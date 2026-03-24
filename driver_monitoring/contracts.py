from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict

from driver_monitoring.reporting import BatchReport, IncidentRecord, SessionReport


class IncidentRecordDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    event_key: str
    source_name: str
    started_at_seconds: float
    ended_at_seconds: float
    max_severity: int
    occurrences: int
    last_message: str


class ScoreResultDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int
    penalties: Dict[str, int]


class SessionReportDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    frame_count: int
    duration_seconds: float
    score_result: ScoreResultDto
    incidents: List[IncidentRecordDto]
    event_counts: Dict[str, int]
    export_json_path: Optional[str] = None
    export_csv_path: Optional[str] = None


class BatchReportDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_directory: str
    session_reports: List[SessionReportDto]
    total_sources: int
    total_incidents: int
    average_score: float
    export_json_path: Optional[str] = None


class AnalyzeVideoRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    config_path: str = "config.toml"


class AnalyzeBatchRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_paths: List[str]
    config_path: str = "config.toml"


def incident_to_dto(incident: IncidentRecord) -> IncidentRecordDto:
    return IncidentRecordDto(
        event_type=incident.event_type,
        event_key=incident.event_key,
        source_name=incident.source_name,
        started_at_seconds=incident.started_at_seconds,
        ended_at_seconds=incident.ended_at_seconds,
        max_severity=incident.max_severity,
        occurrences=incident.occurrences,
        last_message=incident.last_message,
    )


def session_report_to_dto(report: SessionReport) -> SessionReportDto:
    return SessionReportDto(
        source_name=report.source_name,
        frame_count=report.frame_count,
        duration_seconds=report.duration_seconds,
        score_result=ScoreResultDto(
            score=report.score_result.score,
            penalties=dict(report.score_result.penalties),
        ),
        incidents=[incident_to_dto(incident) for incident in report.incidents],
        event_counts=dict(report.event_counts),
        export_json_path=report.export_json_path,
        export_csv_path=report.export_csv_path,
    )


def batch_report_to_dto(report: BatchReport) -> BatchReportDto:
    return BatchReportDto(
        output_directory=report.output_directory,
        session_reports=[session_report_to_dto(session_report) for session_report in report.session_reports],
        total_sources=report.total_sources,
        total_incidents=report.total_incidents,
        average_score=report.average_score,
        export_json_path=report.export_json_path,
    )
