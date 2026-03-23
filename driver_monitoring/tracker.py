from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from deep_sort_realtime.deepsort_tracker import DeepSort

from driver_monitoring.detector import Detection


@dataclass
class TrackedObject:
    track_id: int
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    duration_seconds: float
    source_name: str


class Tracker:
    def __init__(self) -> None:
        self._tracker = DeepSort(max_age=20, n_init=1, embedder="mobilenet")
        self._track_started_at: Dict[int, float] = {}
        self._last_source_name: Optional[str] = None

    def update(
        self,
        detections: List[Detection],
        frame,
        frame_time_seconds: float,
        source_name: str,
    ) -> List[TrackedObject]:
        if self._last_source_name != source_name:
            self.reset(source_name)

        deepsort_detections = []
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            deepsort_detections.append(
                ([x1, y1, width, height], detection.confidence, detection.label)
            )

        tracks = self._tracker.update_tracks(deepsort_detections, frame=frame)

        tracked_objects: List[TrackedObject] = []
        active_track_ids = set()

        for track in tracks:
            if getattr(track, "time_since_update", 0) != 0:
                continue

            track_id = int(track.track_id)
            active_track_ids.add(track_id)
            if track_id not in self._track_started_at:
                self._track_started_at[track_id] = frame_time_seconds

            left, top, right, bottom = track.to_ltrb()
            label = track.get_det_class() or "object"
            confidence = self._resolve_confidence(track)
            duration_seconds = max(0.0, frame_time_seconds - self._track_started_at[track_id])

            tracked_objects.append(
                TrackedObject(
                    track_id=track_id,
                    label=str(label),
                    confidence=confidence,
                    bbox=(int(left), int(top), int(right), int(bottom)),
                    duration_seconds=duration_seconds,
                    source_name=source_name,
                )
            )

        stale_ids = set(self._track_started_at) - active_track_ids
        for track_id in stale_ids:
            self._track_started_at.pop(track_id, None)

        return tracked_objects

    def reset(self, source_name: Optional[str] = None) -> None:
        self._tracker = DeepSort(max_age=20, n_init=1, embedder="mobilenet")
        self._track_started_at.clear()
        self._last_source_name = source_name

    @staticmethod
    def _resolve_confidence(track) -> float:
        original_ltwh = getattr(track, "original_ltwh", None)
        if original_ltwh is not None:
            conf = getattr(track, "det_conf", None)
            if conf is not None:
                return float(conf)
        return 1.0
