from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from driver_monitoring.tracker import TrackedObject


LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
MOUTH_WIDTH_INDICES = (78, 308)
MOUTH_HEIGHT_INDICES = (13, 14)
NOSE_TIP_INDEX = 1
CHIN_INDEX = 152


@dataclass
class FaceState:
    driver_present: bool
    gaze_direction: Optional[str] = None
    head_orientation: Optional[str] = None
    face_bbox: Optional[Tuple[int, int, int, int]] = None
    nose_point: Optional[Tuple[int, int]] = None
    eyes_closed_ratio: Optional[float] = None
    eyes_closed: bool = False
    eyes_closed_duration_seconds: float = 0.0
    yawning: bool = False
    yawning_duration_seconds: float = 0.0
    mouth_open_ratio: Optional[float] = None
    looking_off_road: bool = False
    off_road_duration_seconds: float = 0.0


class FaceMonitor:
    def __init__(
        self,
        eye_closed_threshold: float = 0.23,
        yawn_threshold: float = 0.55,
        yaw_threshold: float = 0.035,
        pitch_down_threshold: float = 0.065,
    ) -> None:
        self.eye_closed_threshold = eye_closed_threshold
        self.yawn_threshold = yawn_threshold
        self.yaw_threshold = yaw_threshold
        self.pitch_down_threshold = pitch_down_threshold
        model_path = Path(__file__).resolve().parent / "assets" / "face_landmarker.task"
        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self._state_started_at: Dict[str, Optional[float]] = {
            "eyes_closed": None,
            "yawning": None,
            "off_road": None,
        }

    def analyze(self, frame, tracked_objects: List[TrackedObject], timestamp_seconds: float) -> FaceState:
        frame_height, frame_width = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, int(timestamp_seconds * 1000))

        if not result.face_landmarks:
            driver_present = any(obj.label == "person" for obj in tracked_objects)
            self._reset_inactive_states()
            return FaceState(driver_present=driver_present)

        landmarks = result.face_landmarks[0]
        left_ear = self._compute_eye_aspect_ratio(landmarks, LEFT_EYE_INDICES)
        right_ear = self._compute_eye_aspect_ratio(landmarks, RIGHT_EYE_INDICES)
        eye_ratio = (left_ear + right_ear) / 2.0
        mouth_open_ratio = self._compute_mouth_open_ratio(landmarks)

        orientation = self._estimate_head_orientation(landmarks)
        gaze_direction = "road" if orientation == "road" else orientation
        eyes_closed = eye_ratio < self.eye_closed_threshold
        yawning = mouth_open_ratio > self.yawn_threshold
        looking_off_road = orientation in {"left", "right", "down"}

        eyes_closed_duration = self._update_state_duration("eyes_closed", eyes_closed, timestamp_seconds)
        yawning_duration = self._update_state_duration("yawning", yawning, timestamp_seconds)
        off_road_duration = self._update_state_duration("off_road", looking_off_road, timestamp_seconds)
        face_bbox = self._compute_face_bbox(landmarks, frame_width, frame_height)
        nose_point = self._to_pixel_point(landmarks[NOSE_TIP_INDEX], frame_width, frame_height)

        return FaceState(
            driver_present=True,
            gaze_direction=gaze_direction,
            head_orientation=orientation,
            face_bbox=face_bbox,
            nose_point=nose_point,
            eyes_closed_ratio=eye_ratio,
            eyes_closed=eyes_closed,
            eyes_closed_duration_seconds=eyes_closed_duration,
            yawning=yawning,
            yawning_duration_seconds=yawning_duration,
            mouth_open_ratio=mouth_open_ratio,
            looking_off_road=looking_off_road,
            off_road_duration_seconds=off_road_duration,
        )

    def reset(self) -> None:
        self._reset_inactive_states()

    def close(self) -> None:
        close_method = getattr(self._landmarker, "close", None)
        if callable(close_method):
            close_method()

    def _update_state_duration(self, key: str, active: bool, timestamp_seconds: float) -> float:
        started_at = self._state_started_at[key]
        if active:
            if started_at is None:
                self._state_started_at[key] = timestamp_seconds
                return 0.0
            return max(0.0, timestamp_seconds - started_at)

        self._state_started_at[key] = None
        return 0.0

    def _reset_inactive_states(self) -> None:
        for key in self._state_started_at:
            self._state_started_at[key] = None

    @staticmethod
    def _distance(a, b) -> float:
        return math.dist((a.x, a.y), (b.x, b.y))

    def _compute_eye_aspect_ratio(self, landmarks, indices: List[int]) -> float:
        p1, p2, p3, p4, p5, p6 = (landmarks[index] for index in indices)
        vertical = self._distance(p2, p6) + self._distance(p3, p5)
        horizontal = max(self._distance(p1, p4), 1e-6)
        return vertical / (2.0 * horizontal)

    def _compute_mouth_open_ratio(self, landmarks) -> float:
        left = landmarks[MOUTH_WIDTH_INDICES[0]]
        right = landmarks[MOUTH_WIDTH_INDICES[1]]
        upper = landmarks[MOUTH_HEIGHT_INDICES[0]]
        lower = landmarks[MOUTH_HEIGHT_INDICES[1]]
        width = max(self._distance(left, right), 1e-6)
        height = self._distance(upper, lower)
        return height / width

    def _estimate_head_orientation(self, landmarks) -> str:
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        nose = landmarks[NOSE_TIP_INDEX]
        chin = landmarks[CHIN_INDEX]

        eye_mid_x = (left_eye.x + right_eye.x) / 2.0
        eye_mid_y = (left_eye.y + right_eye.y) / 2.0
        face_height = max(chin.y - eye_mid_y, 1e-6)

        yaw_offset = nose.x - eye_mid_x
        pitch_offset = nose.y - eye_mid_y

        if yaw_offset < -self.yaw_threshold:
            return "left"
        if yaw_offset > self.yaw_threshold:
            return "right"
        if pitch_offset / face_height > self.pitch_down_threshold:
            return "down"
        return "road"

    def _compute_face_bbox(self, landmarks, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        xs = [point.x for point in landmarks]
        ys = [point.y for point in landmarks]
        x1 = max(0, int(min(xs) * frame_width))
        y1 = max(0, int(min(ys) * frame_height))
        x2 = min(frame_width, int(max(xs) * frame_width))
        y2 = min(frame_height, int(max(ys) * frame_height))
        return (x1, y1, x2, y2)

    @staticmethod
    def _to_pixel_point(landmark, frame_width: int, frame_height: int) -> Tuple[int, int]:
        return (int(landmark.x * frame_width), int(landmark.y * frame_height))
