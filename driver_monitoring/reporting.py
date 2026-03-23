from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from driver_monitoring.event_engine import Event
from driver_monitoring.scoring import ScoreResult, ScoringEngine
from driver_monitoring.video_source import FramePacket


@dataclass
class IncidentRecord:
    event_type: str
    event_key: str
    source_name: str
    started_at_seconds: float
    ended_at_seconds: float
    max_severity: int
    occurrences: int
    last_message: str


@dataclass
class SessionLiveState:
    source_name: str
    frame_count: int
    duration_seconds: float
    score_result: ScoreResult
    active_incident_count: int
    closed_incident_count: int


@dataclass
class SessionReport:
    source_name: str
    frame_count: int
    duration_seconds: float
    score_result: ScoreResult
    incidents: List[IncidentRecord]
    event_counts: Dict[str, int]
    export_json_path: Optional[str] = None
    export_csv_path: Optional[str] = None


@dataclass
class BatchReport:
    output_directory: str
    session_reports: List[SessionReport]
    total_sources: int
    total_incidents: int
    average_score: float
    export_json_path: Optional[str] = None


class SessionAggregator:
    def __init__(self, source_name: str, scoring_engine: ScoringEngine) -> None:
        self.source_name = source_name
        self.scoring_engine = scoring_engine
        self.frame_count = 0
        self.duration_seconds = 0.0
        self._active_incidents: Dict[str, IncidentRecord] = {}
        self._closed_incidents: List[IncidentRecord] = []

    def consume(self, packet: FramePacket, events: List[Event]) -> SessionLiveState:
        self.frame_count += 1
        self.duration_seconds = packet.timestamp_seconds

        current_keys = set()
        for event in events:
            event_key = event.event_key or event.event_type
            current_keys.add(event_key)
            if event_key in self._active_incidents:
                incident = self._active_incidents[event_key]
                incident.ended_at_seconds = packet.timestamp_seconds
                incident.max_severity = max(incident.max_severity, event.severity)
                incident.occurrences += 1
                incident.last_message = event.message
            else:
                self._active_incidents[event_key] = IncidentRecord(
                    event_type=event.event_type,
                    event_key=event_key,
                    source_name=self.source_name,
                    started_at_seconds=packet.timestamp_seconds,
                    ended_at_seconds=packet.timestamp_seconds,
                    max_severity=event.severity,
                    occurrences=1,
                    last_message=event.message,
                )

        for event_key in list(self._active_incidents):
            if event_key in current_keys:
                continue
            self._closed_incidents.append(self._active_incidents.pop(event_key))

        return self.get_live_state()

    def get_live_state(self) -> SessionLiveState:
        score_result = self.scoring_engine.calculate_from_incidents(self._all_incidents())
        return SessionLiveState(
            source_name=self.source_name,
            frame_count=self.frame_count,
            duration_seconds=self.duration_seconds,
            score_result=score_result,
            active_incident_count=len(self._active_incidents),
            closed_incident_count=len(self._closed_incidents),
        )

    def finalize(self, final_timestamp_seconds: float) -> SessionReport:
        self.duration_seconds = max(self.duration_seconds, final_timestamp_seconds)
        for incident in self._active_incidents.values():
            incident.ended_at_seconds = self.duration_seconds
            self._closed_incidents.append(incident)
        self._active_incidents.clear()

        incidents = self._all_incidents()
        event_counts: Dict[str, int] = {}
        for incident in incidents:
            event_counts[incident.event_type] = event_counts.get(incident.event_type, 0) + 1

        return SessionReport(
            source_name=self.source_name,
            frame_count=self.frame_count,
            duration_seconds=self.duration_seconds,
            score_result=self.scoring_engine.calculate_from_incidents(incidents),
            incidents=incidents,
            event_counts=event_counts,
        )

    def _all_incidents(self) -> List[IncidentRecord]:
        return [*self._closed_incidents, *self._active_incidents.values()]


class BatchAggregator:
    def __init__(self, output_directory: str) -> None:
        self.output_directory = output_directory
        self._session_reports: List[SessionReport] = []

    def add_session_report(self, report: SessionReport) -> None:
        self._session_reports.append(report)

    def build_report(self) -> BatchReport:
        total_sources = len(self._session_reports)
        total_incidents = sum(len(report.incidents) for report in self._session_reports)
        average_score = 0.0
        if total_sources:
            average_score = sum(report.score_result.score for report in self._session_reports) / total_sources

        return BatchReport(
            output_directory=self.output_directory,
            session_reports=list(self._session_reports),
            total_sources=total_sources,
            total_incidents=total_incidents,
            average_score=average_score,
        )
