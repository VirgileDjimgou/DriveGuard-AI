from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import cv2

from driver_monitoring.event_engine import Event
from driver_monitoring.face_monitor import FaceState
from driver_monitoring.reporting import BatchReport, SessionReport
from driver_monitoring.scoring import ScoreResult
from driver_monitoring.tracker import TrackedObject


class ResultExporter:
    def draw_overlay(
        self,
        frame,
        tracked_objects: List[TrackedObject],
        face_state: FaceState,
        events: List[Event],
        score_result: ScoreResult,
    ):
        for tracked in tracked_objects:
            x1, y1, x2, y2 = tracked.bbox
            color = self._resolve_color(tracked.label)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            cv2.putText(
                frame,
                (
                    f"{tracked.label} #{tracked.track_id} "
                    f"{tracked.confidence * 100:.0f}% "
                    f"{tracked.duration_seconds:.1f}s"
                ),
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        top = 25
        cv2.putText(
            frame,
            f"Driver score: {score_result.score}",
            (10, top),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        top += 25
        cv2.putText(
            frame,
            f"Head: {face_state.head_orientation or 'unknown'} | Gaze: {face_state.gaze_direction or 'unknown'}",
            (10, top),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )

        top += 25
        cv2.putText(
            frame,
            (
                f"Eyes closed: {face_state.eyes_closed} "
                f"({face_state.eyes_closed_duration_seconds:.1f}s) | "
                f"Yawning: {face_state.yawning} "
                f"({face_state.yawning_duration_seconds:.1f}s)"
            ),
            (10, top),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )

        for event in events[:3]:
            top += 25
            cv2.putText(
                frame,
                event.message,
                (10, top),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 165, 255),
                2,
            )

        return frame

    def log_events(self, frame_index: int, tracked_objects: List[TrackedObject], events: List[Event]) -> None:
        for tracked in tracked_objects:
            print(
                f"[frame {frame_index}] {tracked.label} "
                f"(track={tracked.track_id}, confidence={tracked.confidence * 100:.0f}%, "
                f"duration={tracked.duration_seconds:.1f}s)"
            )

        for event in events:
            print(f"[frame {frame_index}] EVENT {event.event_type}: {event.message}")

    @staticmethod
    def _resolve_color(label: str) -> Tuple[int, int, int]:
        if label == "knife":
            return (0, 0, 255)
        if label == "cell phone":
            return (0, 165, 255)
        if label == "seatbelt_present":
            return (0, 255, 255)
        if label == "seatbelt_missing":
            return (0, 0, 200)
        if label == "person":
            return (0, 255, 0)
        return (255, 255, 0)

    def create_output_directory(self, base_directory: str = "outputs") -> Path:
        run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        output_directory = Path(base_directory) / run_name
        output_directory.mkdir(parents=True, exist_ok=True)
        return output_directory

    def export_session_report(self, report: SessionReport, output_directory: Path) -> SessionReport:
        safe_name = self._safe_source_name(report.source_name)
        json_path = output_directory / f"{safe_name}.json"
        csv_path = output_directory / f"{safe_name}_incidents.csv"

        session_payload = asdict(report)
        session_payload["export_json_path"] = str(json_path)
        session_payload["export_csv_path"] = str(csv_path)

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(session_payload, handle, indent=2)

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "event_type",
                    "event_key",
                    "source_name",
                    "started_at_seconds",
                    "ended_at_seconds",
                    "max_severity",
                    "occurrences",
                    "last_message",
                ]
            )
            for incident in report.incidents:
                writer.writerow(
                    [
                        incident.event_type,
                        incident.event_key,
                        incident.source_name,
                        f"{incident.started_at_seconds:.3f}",
                        f"{incident.ended_at_seconds:.3f}",
                        incident.max_severity,
                        incident.occurrences,
                        incident.last_message,
                    ]
                )

        report.export_json_path = str(json_path)
        report.export_csv_path = str(csv_path)
        return report

    def export_batch_report(self, report: BatchReport, output_directory: Path) -> BatchReport:
        json_path = output_directory / "batch_summary.json"
        payload = asdict(report)
        payload["export_json_path"] = str(json_path)
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        report.export_json_path = str(json_path)
        return report

    @staticmethod
    def _safe_source_name(source_name: str) -> str:
        safe = source_name.replace(":", "_").replace("\\", "_").replace("/", "_").replace(" ", "_")
        if safe == "0":
            return "webcam_0"
        return safe
