from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, TYPE_CHECKING

from driver_monitoring.event_engine import Event

if TYPE_CHECKING:
    from driver_monitoring.reporting import IncidentRecord


@dataclass
class ScoreResult:
    score: int
    penalties: Dict[str, int] = field(default_factory=dict)


class ScoringEngine:
    def __init__(self, starting_score: int = 100) -> None:
        self.starting_score = starting_score

    def calculate(self, events: List[Event]) -> ScoreResult:
        penalties: Dict[str, int] = {}
        score = self.starting_score

        for event in events:
            penalties[event.event_type] = penalties.get(event.event_type, 0) + event.severity
            score -= event.severity

        return ScoreResult(score=max(score, 0), penalties=penalties)

    def calculate_from_incidents(self, incidents: Iterable["IncidentRecord"]) -> ScoreResult:
        penalties: Dict[str, int] = {}
        score = self.starting_score

        for incident in incidents:
            penalties[incident.event_type] = penalties.get(incident.event_type, 0) + incident.max_severity
            score -= incident.max_severity

        return ScoreResult(score=max(score, 0), penalties=penalties)
