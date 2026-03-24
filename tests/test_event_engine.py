from __future__ import annotations

import unittest

from driver_monitoring.event_engine import EventEngine
from driver_monitoring.face_monitor import FaceState
from driver_monitoring.tracker import TrackedObject


def make_track(
    track_id: int,
    label: str,
    bbox: tuple[int, int, int, int],
    duration_seconds: float,
) -> TrackedObject:
    return TrackedObject(
        track_id=track_id,
        label=label,
        confidence=0.9,
        bbox=bbox,
        duration_seconds=duration_seconds,
        source_name="clip.mp4",
    )


class EventEngineTests(unittest.TestCase):
    def test_phone_use_requires_driver_association_and_threshold(self) -> None:
        engine = EventEngine(available_labels=["person", "cell phone"])
        face_state = FaceState(driver_present=True, face_bbox=(100, 100, 180, 180))
        tracked_objects = [
            make_track(1, "person", (60, 60, 260, 320), 4.0),
            make_track(2, "cell phone", (120, 120, 160, 170), 3.0),
        ]

        events_initial = engine.evaluate(tracked_objects, face_state, 0.0)
        events_after = engine.evaluate(tracked_objects, face_state, 2.1)

        self.assertIn("PHONE_NEAR_FACE", [event.event_type for event in events_initial])
        self.assertIn("PHONE_USE", [event.event_type for event in events_after])

    def test_incorrect_seatbelt_is_distinct_from_missing(self) -> None:
        engine = EventEngine(available_labels=["seatbelt_present", "seatbelt_incorrect", "seatbelt_missing"])
        face_state = FaceState(driver_present=True, face_bbox=(100, 100, 180, 180))
        tracked_objects = [
            make_track(1, "person", (60, 60, 260, 320), 4.0),
            make_track(2, "seatbelt_incorrect", (120, 200, 200, 280), 2.5),
        ]

        events = engine.evaluate(tracked_objects, face_state, 2.5)

        self.assertIn("SEATBELT_INCORRECT", [event.event_type for event in events])
        self.assertNotIn("NO_SEATBELT", [event.event_type for event in events])

    def test_no_seatbelt_requires_threshold(self) -> None:
        engine = EventEngine(available_labels=["seatbelt_present", "seatbelt_missing"])
        face_state = FaceState(driver_present=True, face_bbox=(100, 100, 180, 180))
        tracked_short = [
            make_track(1, "person", (60, 60, 260, 320), 4.0),
            make_track(2, "seatbelt_missing", (120, 200, 200, 280), 2.0),
        ]
        tracked_long = [
            make_track(1, "person", (60, 60, 260, 320), 4.0),
            make_track(2, "seatbelt_missing", (120, 200, 200, 280), 3.2),
        ]

        events_short = engine.evaluate(tracked_short, face_state, 0.0)
        events_long = engine.evaluate(tracked_long, face_state, 0.0)

        self.assertNotIn("NO_SEATBELT", [event.event_type for event in events_short])
        self.assertIn("NO_SEATBELT", [event.event_type for event in events_long])


if __name__ == "__main__":
    unittest.main()
