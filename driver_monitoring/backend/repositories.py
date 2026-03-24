from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from driver_monitoring.backend.models import AnalysisJob, AnalysisSession, Incident, ReportArtifact, UploadedVideo


class UploadedVideoRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, video: UploadedVideo) -> UploadedVideo:
        self.session.add(video)
        self.session.flush()
        return video

    def get(self, video_id: str) -> Optional[UploadedVideo]:
        return self.session.get(UploadedVideo, video_id)

    def list_by_ids(self, video_ids: list[str]) -> list[UploadedVideo]:
        if not video_ids:
            return []
        stmt = select(UploadedVideo).where(UploadedVideo.id.in_(video_ids))
        rows = list(self.session.scalars(stmt))
        rows_by_id = {row.id: row for row in rows}
        return [rows_by_id[video_id] for video_id in video_ids if video_id in rows_by_id]


class AnalysisJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, job: AnalysisJob) -> AnalysisJob:
        self.session.add(job)
        self.session.flush()
        return job

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        stmt = (
            select(AnalysisJob)
            .options(joinedload(AnalysisJob.sessions), joinedload(AnalysisJob.artifacts))
            .where(AnalysisJob.id == job_id)
        )
        return self.session.scalars(stmt).unique().one_or_none()

    def list_sessions(self, job_id: Optional[str] = None) -> list[AnalysisSession]:
        stmt = (
            select(AnalysisSession)
            .options(joinedload(AnalysisSession.incidents), joinedload(AnalysisSession.artifacts))
            .order_by(AnalysisSession.created_at.desc())
        )
        if job_id:
            stmt = stmt.where(AnalysisSession.job_id == job_id)
        return list(self.session.scalars(stmt).unique())

    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        stmt = (
            select(AnalysisSession)
            .options(joinedload(AnalysisSession.incidents), joinedload(AnalysisSession.artifacts))
            .where(AnalysisSession.id == session_id)
        )
        return self.session.scalars(stmt).unique().one_or_none()

    def get_incidents(self, session_id: str) -> list[Incident]:
        stmt = select(Incident).where(Incident.session_id == session_id).order_by(Incident.started_at_seconds.asc())
        return list(self.session.scalars(stmt))

    def get_artifact(self, artifact_id: str) -> Optional[ReportArtifact]:
        return self.session.get(ReportArtifact, artifact_id)
