from __future__ import annotations

import unittest

from driver_monitoring.event_engine import Event
from driver_monitoring.reporting import IncidentRecord
from driver_monitoring.scoring import ScoringEngine


class ScoringEngineTests(unittest.TestCase):
    def test_calculate_from_events_aggregates_penalties(self) -> None:
        engine = ScoringEngine(starting_score=100)
        result = engine.calculate(
            [
                Event(event_type="PHONE_USE", severity=15, message="a"),
                Event(event_type="DISTRACTION", severity=10, message="b"),
            ]
        )

        self.assertEqual(result.score, 75)
        self.assertEqual(result.penalties["PHONE_USE"], 15)
        self.assertEqual(result.penalties["DISTRACTION"], 10)

    def test_calculate_from_incidents_uses_max_severity_per_incident(self) -> None:
        engine = ScoringEngine(starting_score=100)
        incidents = [
            IncidentRecord("PHONE_USE", "PHONE_USE:1", "clip", 0.0, 2.0, 15, 3, "phone"),
            IncidentRecord("DROWSINESS", "DROWSINESS", "clip", 5.0, 7.0, 20, 4, "eyes"),
        ]

        result = engine.calculate_from_incidents(incidents)

        self.assertEqual(result.score, 65)
        self.assertEqual(result.penalties["PHONE_USE"], 15)
        self.assertEqual(result.penalties["DROWSINESS"], 20)


if __name__ == "__main__":
    unittest.main()
