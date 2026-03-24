from __future__ import annotations

import importlib
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from driver_monitoring.backend.database import get_database_runtime, init_database
from driver_monitoring.reporting import BatchReport, IncidentRecord, SessionReport
from driver_monitoring.runner import RunResult
from driver_monitoring.scoring import ScoreResult


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.config_path = self.temp_path / "config.toml"
        self.db_path = self.temp_path / "backend.db"
        self.outputs_path = self.temp_path / "outputs"
        self.outputs_path.mkdir(parents=True, exist_ok=True)

        self.config_path.write_text(
            textwrap.dedent(
                f"""
                [models]
                primary_model_path = "yolo-Weights/yolov8n.pt"
                seatbelt_model_path = "driver_monitoring/assets/seatbelt_best.pt"
                face_landmarker_path = "driver_monitoring/assets/face_landmarker.task"

                [runtime]
                width = 720
                height = 720
                confidence_threshold = 0.25
                output_directory = "{self.outputs_path.as_posix()}"

                [face]
                eye_closed_threshold = 0.23
                yawn_threshold = 0.55
                yaw_threshold = 0.035
                pitch_down_threshold = 0.065

                [events]
                phone_use_threshold_seconds = 2.0
                off_road_threshold_seconds = 2.0
                eyes_closed_threshold_seconds = 1.5
                yawn_threshold_seconds = 1.0
                seatbelt_incorrect_threshold_seconds = 2.0
                seatbelt_missing_threshold_seconds = 3.0

                [backend]
                database_url = "sqlite:///{self.db_path.as_posix()}"
                redis_url = "redis://localhost:6379/0"
                queue_backend = "inline"
                queue_name = "driveguard-ai-test"
                uploads_directory = "{(self.temp_path / 'uploads').as_posix()}"
                artifacts_directory = "{(self.temp_path / 'artifacts').as_posix()}"
                api_title = "DriveGuard AI Backend Test"
                api_version = "test"
                """
            ).strip(),
            encoding="utf-8",
        )

        os.environ["DRIVEGUARD_CONFIG_PATH"] = str(self.config_path)
        get_database_runtime.cache_clear()
        init_database(str(self.config_path))

        from driver_monitoring import api as api_module

        self.api_module = importlib.reload(api_module)
        self.client = TestClient(self.api_module.app)

    def tearDown(self) -> None:
        self.client.close()
        runtime = get_database_runtime(str(self.config_path))
        runtime.engine.dispose()
        get_database_runtime.cache_clear()
        os.environ.pop("DRIVEGUARD_CONFIG_PATH", None)
        self.temp_dir.cleanup()

    def test_docs_endpoint_is_available(self) -> None:
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Swagger UI", response.text)

    def test_job_creation_persists_completed_job_and_session(self) -> None:
        source_path = str(self.temp_path / "clip.mp4")
        Path(source_path).write_bytes(b"fake video")
        session_json = self.temp_path / "session.json"
        session_csv = self.temp_path / "session.csv"
        batch_json = self.temp_path / "batch.json"
        session_json.write_text("{}", encoding="utf-8")
        session_csv.write_text("event_type\nPHONE_USE\n", encoding="utf-8")
        batch_json.write_text("{}", encoding="utf-8")

        fake_report = SessionReport(
            source_name=source_path,
            frame_count=12,
            duration_seconds=4.0,
            score_result=ScoreResult(score=85, penalties={"PHONE_USE": 15}),
            incidents=[
                IncidentRecord(
                    event_type="PHONE_USE",
                    event_key="PHONE_USE:1",
                    source_name=source_path,
                    started_at_seconds=0.5,
                    ended_at_seconds=2.5,
                    max_severity=15,
                    occurrences=3,
                    last_message="phone near face",
                )
            ],
            event_counts={"PHONE_USE": 1},
            export_json_path=str(session_json),
            export_csv_path=str(session_csv),
        )
        fake_batch = BatchReport(
            output_directory=str(self.outputs_path),
            session_reports=[fake_report],
            total_sources=1,
            total_incidents=1,
            average_score=85.0,
            export_json_path=str(batch_json),
        )
        fake_run_result = RunResult(session_reports=[fake_report], batch_report=fake_batch)
        fake_core_result = SimpleNamespace(run_result=fake_run_result)

        with patch("driver_monitoring.backend.jobs.analyze_video", return_value=fake_core_result):
            response = self.client.post(
                "/analysis-jobs",
                json={
                    "source_type": "video",
                    "source_paths": [source_path],
                    "uploaded_video_ids": [],
                    "config_path": str(self.config_path),
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["total_incidents"], 1)
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(payload["sessions"][0]["score"], 85)

        sessions_response = self.client.get("/sessions")
        self.assertEqual(sessions_response.status_code, 200)
        sessions_payload = sessions_response.json()
        self.assertEqual(len(sessions_payload), 1)
        self.assertEqual(sessions_payload[0]["source_name"], source_path)

        incidents_response = self.client.get(f"/sessions/{sessions_payload[0]['id']}/incidents")
        self.assertEqual(incidents_response.status_code, 200)
        incidents_payload = incidents_response.json()
        self.assertEqual(len(incidents_payload), 1)
        self.assertEqual(incidents_payload[0]["event_type"], "PHONE_USE")


if __name__ == "__main__":
    unittest.main()
