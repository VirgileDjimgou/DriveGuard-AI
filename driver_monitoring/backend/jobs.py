from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from redis import Redis

from driver_monitoring.backend.database import load_backend_config, session_scope
from driver_monitoring.backend.models import ReportArtifact
from driver_monitoring.backend.repositories import AnalysisJobRepository
from driver_monitoring.backend.services import copy_artifact_to_backend, persist_session_report, reset_job_results, resolve_job_source_paths
from driver_monitoring.core import analyze_batch, analyze_video


def get_queue(config_path: str = "config.toml") -> Any:
    app_config = load_backend_config(config_path)
    connection = Redis.from_url(app_config.backend.redis_url)
    from rq import Queue

    return Queue(app_config.backend.queue_name, connection=connection)


def enqueue_analysis_job(job_id: str, config_path: str = "config.toml") -> Optional[str]:
    app_config = load_backend_config(config_path)
    if app_config.backend.queue_backend == "inline":
        process_analysis_job(job_id, config_path)
        return None
    if app_config.backend.queue_backend == "redis":
        connection = Redis.from_url(app_config.backend.redis_url)
        payload = json.dumps({"job_id": job_id, "config_path": config_path})
        connection.rpush(app_config.backend.queue_name, payload)
        return f"redis:{job_id}"

    queue = get_queue(config_path)
    job = queue.enqueue(
        "driver_monitoring.backend.jobs.process_analysis_job",
        job_id,
        config_path,
        job_timeout="2h",
    )
    return job.id


def process_analysis_job(job_id: str, config_path: str = "config.toml") -> None:
    with session_scope(config_path) as session:
        repository = AnalysisJobRepository(session)
        job = repository.get(job_id)
        if job is None:
            raise ValueError(f"Analysis job '{job_id}' does not exist.")

        reset_job_results(job)
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        source_paths = resolve_job_source_paths(session, job)

        try:
            if job.source_type == "video":
                core_result = analyze_video(source_paths[0], job.config_path)
            else:
                core_result = analyze_batch(source_paths, job.config_path)

            batch_report = core_result.run_result.batch_report
            job.total_sources = batch_report.total_sources
            job.total_incidents = batch_report.total_incidents
            job.average_score = batch_report.average_score
            if batch_report.export_json_path:
                copied_path = copy_artifact_to_backend(batch_report.export_json_path, config_path)
                job.batch_report_export_path = copied_path
                session.add(
                    ReportArtifact(
                        job_id=job.id,
                        session_id=None,
                        artifact_type="batch_json",
                        path=copied_path,
                    )
                )

            path_by_source_name = _build_source_lookup(source_paths)
            for report in batch_report.session_reports:
                persist_session_report(
                    session,
                    job,
                    path_by_source_name.get(report.source_name),
                    report,
                )

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(exc)
            raise


def _build_source_lookup(source_paths: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for source_path in source_paths:
        lookup[source_path] = source_path
    return lookup
