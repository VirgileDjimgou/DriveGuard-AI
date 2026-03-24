from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from driver_monitoring.backend.models import AnalysisJob, AnalysisSession, Incident, ReportArtifact, UploadedVideo
from driver_monitoring.backend.repositories import AnalysisJobRepository, UploadedVideoRepository
from driver_monitoring.backend.schemas import CreateAnalysisJobRequestDto
from driver_monitoring.config import load_app_config


class BackendValidationError(ValueError):
    pass


def store_uploaded_video(session: Session, upload: UploadFile, config_path: str = "config.toml") -> UploadedVideo:
    app_config = load_app_config(config_path)
    uploads_directory = Path(app_config.backend.uploads_directory)
    uploads_directory.mkdir(parents=True, exist_ok=True)

    safe_name = Path(upload.filename or "video.bin").name
    stored_path = uploads_directory / f"upload_{uuid4()}_{safe_name}"

    size_bytes = 0
    with stored_path.open("wb") as destination:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            destination.write(chunk)

    video = UploadedVideo(
        original_filename=safe_name,
        stored_path=str(stored_path),
        content_type=upload.content_type,
        size_bytes=size_bytes,
    )
    return UploadedVideoRepository(session).add(video)


def create_analysis_job(session: Session, payload: CreateAnalysisJobRequestDto) -> AnalysisJob:
    _validate_job_sources(session, payload)
    job = AnalysisJob(
        status="queued",
        source_type=payload.source_type,
        source_paths=list(payload.source_paths),
        uploaded_video_ids=list(payload.uploaded_video_ids),
        config_path=payload.config_path,
    )
    return AnalysisJobRepository(session).add(job)


def _validate_job_sources(session: Session, payload: CreateAnalysisJobRequestDto) -> None:
    if payload.uploaded_video_ids:
        videos = UploadedVideoRepository(session).list_by_ids(payload.uploaded_video_ids)
        if len(videos) != len(payload.uploaded_video_ids):
            raise BackendValidationError("One or more uploaded video ids do not exist.")


def resolve_job_source_paths(session: Session, job: AnalysisJob) -> list[str]:
    uploaded_videos = UploadedVideoRepository(session).list_by_ids(job.uploaded_video_ids)
    uploaded_paths = [video.stored_path for video in uploaded_videos]
    return [*job.source_paths, *uploaded_paths]


def reset_job_results(job: AnalysisJob) -> None:
    job.sessions.clear()
    job.artifacts.clear()
    job.total_sources = 0
    job.total_incidents = 0
    job.average_score = 0.0
    job.batch_report_export_path = None
    job.error_message = None


def persist_session_report(
    session: Session,
    job: AnalysisJob,
    source_path: Optional[str],
    report: object,
) -> AnalysisSession:
    from driver_monitoring.reporting import SessionReport

    if not isinstance(report, SessionReport):
        raise TypeError("Expected SessionReport.")

    output_directory = ""
    if report.export_json_path:
        output_directory = str(Path(report.export_json_path).parent)
    elif report.export_csv_path:
        output_directory = str(Path(report.export_csv_path).parent)

    session_row = AnalysisSession(
        job_id=job.id,
        source_name=report.source_name,
        source_path=source_path,
        frame_count=report.frame_count,
        duration_seconds=report.duration_seconds,
        score=report.score_result.score,
        penalties={key: int(value) for key, value in report.score_result.penalties.items()},
        event_counts={key: int(value) for key, value in report.event_counts.items()},
        output_directory=output_directory,
        export_json_path=report.export_json_path,
        export_csv_path=report.export_csv_path,
    )
    session.add(session_row)
    session.flush()

    for incident in report.incidents:
        session.add(
            Incident(
                session_id=session_row.id,
                event_type=incident.event_type,
                event_key=incident.event_key,
                source_name=incident.source_name,
                started_at_seconds=incident.started_at_seconds,
                ended_at_seconds=incident.ended_at_seconds,
                max_severity=incident.max_severity,
                occurrences=incident.occurrences,
                last_message=incident.last_message,
            )
        )

    if report.export_json_path:
        session.add(
            ReportArtifact(
                job_id=job.id,
                session_id=session_row.id,
                artifact_type="session_json",
                path=report.export_json_path,
            )
        )
    if report.export_csv_path:
        session.add(
            ReportArtifact(
                job_id=job.id,
                session_id=session_row.id,
                artifact_type="session_csv",
                path=report.export_csv_path,
            )
        )

    session.flush()
    return session_row


def copy_artifact_to_backend(path: str, config_path: str = "config.toml") -> str:
    app_config = load_app_config(config_path)
    artifacts_directory = Path(app_config.backend.artifacts_directory)
    artifacts_directory.mkdir(parents=True, exist_ok=True)
    source = Path(path)
    destination = artifacts_directory / source.name
    if source.exists() and source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
        return str(destination)
    return str(source)
