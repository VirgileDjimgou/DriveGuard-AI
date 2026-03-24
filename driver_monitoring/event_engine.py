from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from driver_monitoring.face_monitor import FaceState
from driver_monitoring.tracker import TrackedObject


@dataclass
class Event:
    event_type: str
    severity: int
    message: str
    event_key: Optional[str] = None


class EventEngine:
    def __init__(
        self,
        available_labels: Optional[Sequence[str]] = None,
        phone_use_threshold_seconds: float = 2.0,
        off_road_threshold_seconds: float = 2.0,
        eyes_closed_threshold_seconds: float = 1.5,
        yawn_threshold_seconds: float = 1.0,
        seatbelt_incorrect_threshold_seconds: float = 2.0,
        seatbelt_missing_threshold_seconds: float = 3.0,
    ) -> None:
        self.phone_use_threshold_seconds = phone_use_threshold_seconds
        self.off_road_threshold_seconds = off_road_threshold_seconds
        self.eyes_closed_threshold_seconds = eyes_closed_threshold_seconds
        self.yawn_threshold_seconds = yawn_threshold_seconds
        self.seatbelt_incorrect_threshold_seconds = seatbelt_incorrect_threshold_seconds
        self.seatbelt_missing_threshold_seconds = seatbelt_missing_threshold_seconds
        self.seatbelt_present_labels = {"seat belt", "seatbelt", "safety belt", "seatbelt_present"}
        self.seatbelt_incorrect_labels = {"seatbelt_incorrect"}
        self.seatbelt_missing_labels = {"seatbelt_missing"}
        self.supports_seatbelt_detection = any(
            label in self.seatbelt_present_labels
            or label in self.seatbelt_incorrect_labels
            or label in self.seatbelt_missing_labels
            for label in (available_labels or [])
        )
        self._phone_near_face_started_at: Dict[int, float] = {}
        self._seatbelt_missing_started_at: Optional[float] = None

    def reset(self) -> None:
        self._phone_near_face_started_at.clear()
        self._seatbelt_missing_started_at = None

    def evaluate(
        self,
        tracked_objects: List[TrackedObject],
        face_state: FaceState,
        timestamp_seconds: float,
    ) -> List[Event]:
        events: List[Event] = []
        labels = {obj.label for obj in tracked_objects}
        active_phone_tracks: Set[int] = set()
        driver_bbox = self._find_driver_bbox(tracked_objects, face_state)

        if face_state.driver_present:
            for tracked in tracked_objects:
                if tracked.label != "cell phone":
                    continue

                if self._is_phone_associated_with_driver(tracked, face_state, driver_bbox):
                    active_phone_tracks.add(tracked.track_id)
                    started_at = self._phone_near_face_started_at.setdefault(
                        tracked.track_id,
                        timestamp_seconds,
                    )
                    near_face_duration = max(0.0, timestamp_seconds - started_at)

                    if near_face_duration >= self.phone_use_threshold_seconds:
                        events.append(
                            Event(
                                event_type="PHONE_USE",
                                severity=15,
                                message=(
                                    f"Cell phone near driver face for {near_face_duration:.1f}s "
                                    f"(track {tracked.track_id})."
                                ),
                                event_key=f"PHONE_USE:{tracked.track_id}",
                            )
                        )
                    else:
                        events.append(
                            Event(
                                event_type="PHONE_NEAR_FACE",
                                severity=0,
                                message=(
                                    f"Cell phone near driver face for {near_face_duration:.1f}s "
                                    f"(track {tracked.track_id})."
                                ),
                                event_key=f"PHONE_NEAR_FACE:{tracked.track_id}",
                            )
                        )
                elif tracked.duration_seconds >= self.phone_use_threshold_seconds:
                    events.append(
                        Event(
                            event_type="PHONE_VISIBLE",
                            severity=0,
                            message=(
                                "Cell phone tracked away from the driver face for "
                                f"{tracked.duration_seconds:.1f}s."
                            ),
                            event_key=f"PHONE_VISIBLE:{tracked.track_id}",
                        )
                    )
                else:
                    events.append(
                        Event(
                            event_type="PHONE_DETECTED_SHORT",
                            severity=0,
                            message=f"Cell phone visible for {tracked.duration_seconds:.1f}s.",
                            event_key=f"PHONE_DETECTED_SHORT:{tracked.track_id}",
                        )
                    )

        stale_phone_tracks = set(self._phone_near_face_started_at) - active_phone_tracks
        for track_id in stale_phone_tracks:
            self._phone_near_face_started_at.pop(track_id, None)

        if "knife" in labels:
            events.append(
                Event(
                    event_type="SHARP_OBJECT_DETECTED",
                    severity=10,
                    message="Knife detected in frame.",
                    event_key="SHARP_OBJECT_DETECTED",
                )
            )

        if face_state.looking_off_road and face_state.off_road_duration_seconds >= self.off_road_threshold_seconds:
            events.append(
                Event(
                    event_type="DISTRACTION",
                    severity=10,
                    message=f"Driver looking off road for {face_state.off_road_duration_seconds:.1f}s.",
                    event_key="DISTRACTION",
                )
            )

        if face_state.eyes_closed and face_state.eyes_closed_duration_seconds >= self.eyes_closed_threshold_seconds:
            events.append(
                Event(
                    event_type="DROWSINESS",
                    severity=20,
                    message=f"Eyes closed for {face_state.eyes_closed_duration_seconds:.1f}s.",
                    event_key="DROWSINESS",
                )
            )

        if face_state.yawning and face_state.yawning_duration_seconds >= self.yawn_threshold_seconds:
            events.append(
                Event(
                    event_type="YAWNING",
                    severity=8,
                    message=f"Yawning detected for {face_state.yawning_duration_seconds:.1f}s.",
                    event_key="YAWNING",
                )
            )

        seatbelt_incorrect_tracks = [
            tracked
            for tracked in tracked_objects
            if tracked.label in self.seatbelt_incorrect_labels and self._belongs_to_driver(tracked, driver_bbox)
        ]
        seatbelt_present_detected = any(
            tracked.label in self.seatbelt_present_labels and self._belongs_to_driver(tracked, driver_bbox)
            for tracked in tracked_objects
        )
        seatbelt_missing_tracks = [
            tracked
            for tracked in tracked_objects
            if tracked.label in self.seatbelt_missing_labels and self._belongs_to_driver(tracked, driver_bbox)
        ]

        if seatbelt_incorrect_tracks:
            self._seatbelt_missing_started_at = None
            for tracked in seatbelt_incorrect_tracks:
                if tracked.duration_seconds >= self.seatbelt_incorrect_threshold_seconds:
                    events.append(
                        Event(
                            event_type="SEATBELT_INCORRECT",
                            severity=10,
                            message=f"Seatbelt worn incorrectly for {tracked.duration_seconds:.1f}s.",
                            event_key=f"SEATBELT_INCORRECT:{tracked.track_id}",
                        )
                    )
        elif seatbelt_missing_tracks:
            self._seatbelt_missing_started_at = None
            for tracked in seatbelt_missing_tracks:
                if tracked.duration_seconds >= self.seatbelt_missing_threshold_seconds:
                    events.append(
                        Event(
                            event_type="NO_SEATBELT",
                            severity=15,
                            message=f"Seatbelt missing for {tracked.duration_seconds:.1f}s.",
                            event_key=f"NO_SEATBELT:{tracked.track_id}",
                        )
                    )
        elif face_state.driver_present and self.supports_seatbelt_detection and not seatbelt_present_detected:
            if self._seatbelt_missing_started_at is None:
                self._seatbelt_missing_started_at = timestamp_seconds
            missing_duration = max(0.0, timestamp_seconds - self._seatbelt_missing_started_at)
            if missing_duration >= self.seatbelt_missing_threshold_seconds:
                events.append(
                    Event(
                        event_type="NO_SEATBELT",
                        severity=15,
                        message=f"Seatbelt not detected for {missing_duration:.1f}s.",
                        event_key="NO_SEATBELT:implicit",
                    )
                )
        else:
            self._seatbelt_missing_started_at = None

        return events

    @staticmethod
    def _is_near_face(tracked: TrackedObject, face_state: FaceState) -> bool:
        if not face_state.face_bbox:
            return False

        face_x1, face_y1, face_x2, face_y2 = face_state.face_bbox
        face_width = face_x2 - face_x1
        face_height = face_y2 - face_y1
        expand_x = int(face_width * 0.35)
        expand_y = int(face_height * 0.35)
        expanded_face = (
            face_x1 - expand_x,
            face_y1 - expand_y,
            face_x2 + expand_x,
            face_y2 + expand_y,
        )
        return EventEngine._boxes_intersect(tracked.bbox, expanded_face)

    @staticmethod
    def _belongs_to_driver(
        tracked: TrackedObject,
        driver_bbox: Optional[tuple[int, int, int, int]],
    ) -> bool:
        if driver_bbox is None:
            return True

        x1, y1, x2, y2 = driver_bbox
        width = x2 - x1
        height = y2 - y1
        expanded_driver = (
            x1 - int(width * 0.15),
            y1 - int(height * 0.15),
            x2 + int(width * 0.15),
            y2 + int(height * 0.15),
        )
        return EventEngine._boxes_intersect(tracked.bbox, expanded_driver)

    @classmethod
    def _is_phone_associated_with_driver(
        cls,
        tracked: TrackedObject,
        face_state: FaceState,
        driver_bbox: Optional[tuple[int, int, int, int]],
    ) -> bool:
        return cls._is_near_face(tracked, face_state) and cls._belongs_to_driver(tracked, driver_bbox)

    @staticmethod
    def _find_driver_bbox(
        tracked_objects: List[TrackedObject],
        face_state: FaceState,
    ) -> Optional[tuple[int, int, int, int]]:
        if face_state.face_bbox is None:
            return None

        best_bbox: Optional[tuple[int, int, int, int]] = None
        best_overlap = 0
        for tracked in tracked_objects:
            if tracked.label != "person":
                continue
            overlap = EventEngine._intersection_area(tracked.bbox, face_state.face_bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_bbox = tracked.bbox
        return best_bbox

    @staticmethod
    def _intersection_area(a, b) -> int:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        width = max(0, min(ax2, bx2) - max(ax1, bx1))
        height = max(0, min(ay2, by2) - max(ay1, by1))
        return width * height

    @staticmethod
    def _boxes_intersect(a, b) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1
