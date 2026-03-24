from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiMessageDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class UploadedVideoDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    original_filename: str
    stored_path: str
    content_type: Optional[str]
    size_bytes: int
    created_at: datetime


class CreateAnalysisJobRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["video", "batch"] = "video"
    source_paths: list[str] = Field(default_factory=list)
    uploaded_video_ids: list[str] = Field(default_factory=list)
    config_path: str = "config.toml"

    @model_validator(mode="after")
    def validate_sources(self) -> "CreateAnalysisJobRequestDto":
        if not self.source_paths and not self.uploaded_video_ids:
            raise ValueError("At least one source path or uploaded video id is required.")
        if self.source_type == "video" and len(self.source_paths) + len(self.uploaded_video_ids) != 1:
            raise ValueError("Video jobs require exactly one source.")
        return self


class QueueMetadataDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    queue_name: str
    queue_job_id: Optional[str] = None


class ReportArtifactDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    job_id: str
    session_id: Optional[str]
    artifact_type: str
    path: str
    created_at: datetime


class IncidentDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    session_id: str
    event_type: str
    event_key: str
    source_name: str
    started_at_seconds: float
    ended_at_seconds: float
    max_severity: int
    occurrences: int
    last_message: str


class AnalysisSessionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    job_id: str
    source_name: str
    source_path: Optional[str]
    frame_count: int
    duration_seconds: float
    score: int
    penalties: dict[str, int]
    event_counts: dict[str, int]
    output_directory: str
    export_json_path: Optional[str]
    export_csv_path: Optional[str]
    created_at: datetime
    incidents: list[IncidentDto] = Field(default_factory=list)
    artifacts: list[ReportArtifactDto] = Field(default_factory=list)


class AnalysisJobDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    status: str
    source_type: str
    source_paths: list[str]
    uploaded_video_ids: list[str]
    config_path: str
    queue_job_id: Optional[str]
    error_message: Optional[str]
    total_sources: int
    total_incidents: int
    average_score: float
    batch_report_export_path: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    sessions: list[AnalysisSessionDto] = Field(default_factory=list)
    artifacts: list[ReportArtifactDto] = Field(default_factory=list)


class HealthDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    queue_backend: str
    database_url: str
