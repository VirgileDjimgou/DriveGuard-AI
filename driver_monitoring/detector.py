from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ultralytics import YOLO


SEATBELT_LABEL_MAP: Dict[str, str] = {
    "correct_seatbelt": "seatbelt_present",
    "incorrect_seatbelt": "seatbelt_missing",
    "no_seatbelt": "seatbelt_missing",
}


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]


class YoloDetector:
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.25,
        label_map: Optional[Dict[str, str]] = None,
        allowed_labels: Optional[Sequence[str]] = None,
    ) -> None:
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.label_map = label_map or {}
        self.allowed_labels = set(allowed_labels) if allowed_labels is not None else None
        self._model = YOLO(model_path)

    @property
    def class_names(self) -> Sequence[str]:
        names = self._model.names
        if isinstance(names, dict):
            return [names[i] for i in sorted(names)]
        return names

    def detect(self, frame) -> List[Detection]:
        results = self._model(frame, stream=True, verbose=False)
        detections: List[Detection] = []

        for result in results:
            for box in result.boxes:
                confidence = float(box.conf[0])
                if confidence < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cls = int(box.cls[0])
                raw_label = self.class_names[cls]
                label = self.label_map.get(raw_label, raw_label)
                if self.allowed_labels is not None and label not in self.allowed_labels:
                    continue
                detections.append(
                    Detection(
                        label=label,
                        confidence=confidence,
                        bbox=(x1, y1, x2, y2),
                    )
                )

        return detections


def resolve_default_model_path() -> str:
    candidate_paths = [
        Path("yolo-Weights") / "yolov8n.pt",
        Path("yolov8n.pt"),
    ]
    for path in candidate_paths:
        if path.exists():
            return str(path)
    return str(candidate_paths[0])


def resolve_seatbelt_model_path() -> Optional[str]:
    candidate_paths = [
        Path("driver_monitoring") / "assets" / "seatbelt_best.pt",
        Path("assets") / "seatbelt_best.pt",
    ]
    for path in candidate_paths:
        if path.exists():
            return str(path)
    return None


class CompositeDetector:
    def __init__(
        self,
        primary_model_path: str,
        confidence_threshold: float = 0.25,
        seatbelt_model_path: Optional[str] = None,
    ) -> None:
        self.primary_detector = YoloDetector(
            model_path=primary_model_path,
            confidence_threshold=confidence_threshold,
        )
        self.seatbelt_detector: Optional[YoloDetector] = None
        if seatbelt_model_path:
            self.seatbelt_detector = YoloDetector(
                model_path=seatbelt_model_path,
                confidence_threshold=confidence_threshold,
                label_map=SEATBELT_LABEL_MAP,
                allowed_labels=("seatbelt_present", "seatbelt_missing"),
            )

    @property
    def class_names(self) -> Sequence[str]:
        labels = list(self.primary_detector.class_names)
        if self.seatbelt_detector is not None:
            for label in ("seatbelt_present", "seatbelt_missing"):
                if label not in labels:
                    labels.append(label)
        return labels

    @property
    def seatbelt_model_enabled(self) -> bool:
        return self.seatbelt_detector is not None

    def detect(self, frame) -> List[Detection]:
        detections = self.primary_detector.detect(frame)
        if self.seatbelt_detector is not None:
            detections.extend(self.seatbelt_detector.detect(frame))
        return detections
