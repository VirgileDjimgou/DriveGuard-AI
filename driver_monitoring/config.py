from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import tomllib

from driver_monitoring.detector import resolve_default_model_path, resolve_seatbelt_model_path


@dataclass
class ModelSettings:
    primary_model_path: str
    seatbelt_model_path: Optional[str]
    face_landmarker_path: str


@dataclass
class RuntimeSettings:
    width: int
    height: int
    confidence_threshold: float
    output_directory: str


@dataclass
class FaceSettings:
    eye_closed_threshold: float
    yawn_threshold: float
    yaw_threshold: float
    pitch_down_threshold: float


@dataclass
class EventSettings:
    phone_use_threshold_seconds: float
    off_road_threshold_seconds: float
    eyes_closed_threshold_seconds: float
    yawn_threshold_seconds: float
    seatbelt_incorrect_threshold_seconds: float
    seatbelt_missing_threshold_seconds: float


@dataclass
class AppConfig:
    models: ModelSettings
    runtime: RuntimeSettings
    face: FaceSettings
    events: EventSettings


def load_app_config(config_path: str = "config.toml") -> AppConfig:
    path = Path(config_path)
    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    models_payload = payload.get("models", {})
    runtime_payload = payload.get("runtime", {})
    face_payload = payload.get("face", {})
    event_payload = payload.get("events", {})

    primary_model_path = _resolve_existing_path(
        models_payload.get("primary_model_path"),
        resolve_default_model_path(),
    )
    seatbelt_model_path = _resolve_optional_existing_path(
        models_payload.get("seatbelt_model_path"),
        resolve_seatbelt_model_path(),
    )
    face_landmarker_path = _resolve_existing_path(
        models_payload.get("face_landmarker_path"),
        "driver_monitoring/assets/face_landmarker.task",
    )

    return AppConfig(
        models=ModelSettings(
            primary_model_path=primary_model_path,
            seatbelt_model_path=seatbelt_model_path,
            face_landmarker_path=face_landmarker_path,
        ),
        runtime=RuntimeSettings(
            width=int(runtime_payload.get("width", 720)),
            height=int(runtime_payload.get("height", 720)),
            confidence_threshold=float(runtime_payload.get("confidence_threshold", 0.25)),
            output_directory=str(runtime_payload.get("output_directory", "outputs")),
        ),
        face=FaceSettings(
            eye_closed_threshold=float(face_payload.get("eye_closed_threshold", 0.23)),
            yawn_threshold=float(face_payload.get("yawn_threshold", 0.55)),
            yaw_threshold=float(face_payload.get("yaw_threshold", 0.035)),
            pitch_down_threshold=float(face_payload.get("pitch_down_threshold", 0.065)),
        ),
        events=EventSettings(
            phone_use_threshold_seconds=float(event_payload.get("phone_use_threshold_seconds", 2.0)),
            off_road_threshold_seconds=float(event_payload.get("off_road_threshold_seconds", 2.0)),
            eyes_closed_threshold_seconds=float(event_payload.get("eyes_closed_threshold_seconds", 1.5)),
            yawn_threshold_seconds=float(event_payload.get("yawn_threshold_seconds", 1.0)),
            seatbelt_incorrect_threshold_seconds=float(
                event_payload.get("seatbelt_incorrect_threshold_seconds", 2.0)
            ),
            seatbelt_missing_threshold_seconds=float(
                event_payload.get("seatbelt_missing_threshold_seconds", 3.0)
            ),
        ),
    )


def _resolve_existing_path(configured_path: Optional[str], fallback_path: str) -> str:
    if configured_path and Path(configured_path).exists():
        return configured_path
    return fallback_path


def _resolve_optional_existing_path(configured_path: Optional[str], fallback_path: Optional[str]) -> Optional[str]:
    if configured_path and Path(configured_path).exists():
        return configured_path
    if fallback_path and Path(fallback_path).exists():
        return fallback_path
    return None
