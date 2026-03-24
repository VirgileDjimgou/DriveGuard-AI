from __future__ import annotations

import unittest

import numpy as np

from driver_monitoring.event_engine import Event
from driver_monitoring.reporting import SessionAggregator
from driver_monitoring.scoring import ScoringEngine
from driver_monitoring.video_source import FramePacket


class ReportingTests(unittest.TestCase):
    def test_session_aggregator_merges_repeated_event_keys(self) -> None:
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        aggregator = SessionAggregator("clip.mp4", ScoringEngine())

        packet_1 = FramePacket(0, frame, "clip.mp4", 0.0, 30.0)
        packet_2 = FramePacket(1, frame, "clip.mp4", 1.0, 30.0)

        aggregator.consume(packet_1, [Event("PHONE_USE", 15, "phone", "PHONE_USE:1")])
        aggregator.consume(packet_2, [Event("PHONE_USE", 15, "phone", "PHONE_USE:1")])
        report = aggregator.finalize(1.0)

        self.assertEqual(len(report.incidents), 1)
        self.assertEqual(report.incidents[0].occurrences, 2)
        self.assertEqual(report.score_result.score, 85)

    def test_session_aggregator_closes_missing_events(self) -> None:
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        aggregator = SessionAggregator("clip.mp4", ScoringEngine())

        packet_1 = FramePacket(0, frame, "clip.mp4", 0.0, 30.0)
        packet_2 = FramePacket(1, frame, "clip.mp4", 1.0, 30.0)

        aggregator.consume(packet_1, [Event("DISTRACTION", 10, "off road", "DISTRACTION")])
        aggregator.consume(packet_2, [])
        report = aggregator.finalize(1.0)

        self.assertEqual(len(report.incidents), 1)
        self.assertEqual(report.incidents[0].event_type, "DISTRACTION")
        self.assertEqual(report.event_counts["DISTRACTION"], 1)


if __name__ == "__main__":
    unittest.main()
