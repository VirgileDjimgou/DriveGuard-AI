from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class UploadedVideo(Base):
    __tablename__ = "uploaded_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(32), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    uploaded_video_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    config_path: Mapped[str] = mapped_column(Text)
    queue_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_sources: Mapped[int] = mapped_column(Integer, default=0)
    total_incidents: Mapped[int] = mapped_column(Integer, default=0)
    average_score: Mapped[float] = mapped_column(Float, default=0.0)
    batch_report_export_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["AnalysisSession"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["ReportArtifact"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id"), index=True)
    source_name: Mapped[str] = mapped_column(Text)
    source_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[int] = mapped_column(Integer, default=100)
    penalties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    event_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_directory: Mapped[str] = mapped_column(Text)
    export_json_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    export_csv_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[AnalysisJob] = relationship(back_populates="sessions")
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list["ReportArtifact"]] = relationship(back_populates="session")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_key: Mapped[str] = mapped_column(String(128))
    source_name: Mapped[str] = mapped_column(Text)
    started_at_seconds: Mapped[float] = mapped_column(Float)
    ended_at_seconds: Mapped[float] = mapped_column(Float)
    max_severity: Mapped[int] = mapped_column(Integer)
    occurrences: Mapped[int] = mapped_column(Integer)
    last_message: Mapped[str] = mapped_column(Text)

    session: Mapped[AnalysisSession] = relationship(back_populates="incidents")


class ReportArtifact(Base):
    __tablename__ = "report_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id"), index=True)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("analysis_sessions.id"), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[AnalysisJob] = relationship(back_populates="artifacts")
    session: Mapped[Optional[AnalysisSession]] = relationship(back_populates="artifacts")
