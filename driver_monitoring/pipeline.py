from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from driver_monitoring.detector import CompositeDetector, resolve_default_model_path, resolve_seatbelt_model_path
from driver_monitoring.event_engine import Event, EventEngine
from driver_monitoring.export import ResultExporter
from driver_monitoring.face_monitor import FaceMonitor, FaceState
from driver_monitoring.reporting import BatchAggregator, BatchReport, SessionAggregator, SessionLiveState, SessionReport
from driver_monitoring.scoring import ScoreResult, ScoringEngine
from driver_monitoring.tracker import Tracker, TrackedObject
from driver_monitoring.video_source import BaseVideoSource, FramePacket, create_video_source


@dataclass
class PipelineConfig:
    source_mode: str = "webcam"
    source: Union[int, str, Sequence[str]] = 0
    model_path: str = resolve_default_model_path()
    seatbelt_model_path: Optional[str] = resolve_seatbelt_model_path()
    confidence_threshold: float = 0.25
    width: int = 720
    height: int = 720
    output_directory: Optional[str] = None


@dataclass
class FrameAnalysis:
    packet: FramePacket
    tracked_objects: list[TrackedObject]
    face_state: FaceState
    events: list[Event]
    session_state: SessionLiveState
    score_result: ScoreResult
    annotated_frame: object


class DriverMonitoringPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.detector = CompositeDetector(
            primary_model_path=config.model_path,
            confidence_threshold=config.confidence_threshold,
            seatbelt_model_path=config.seatbelt_model_path,
        )
        self.tracker = Tracker()
        self.face_monitor = FaceMonitor()
        self.event_engine = EventEngine(available_labels=self.detector.class_names)
        self.scoring = ScoringEngine()
        self.exporter = ResultExporter()
        self.output_directory = (
            Path(config.output_directory)
            if config.output_directory
            else self.exporter.create_output_directory()
        )
        self.batch_aggregator = BatchAggregator(str(self.output_directory))
        self.current_session: Optional[SessionAggregator] = None
        self.current_source_name: Optional[str] = None
        self._completed_reports: List[SessionReport] = []

    def create_source(self) -> BaseVideoSource:
        return create_video_source(
            mode=self.config.source_mode,
            source=self.config.source,
            width=self.config.width,
            height=self.config.height,
        )

    def process_packet(self, packet: FramePacket) -> FrameAnalysis:
        self._ensure_source_session(packet.source_name)
        detections = self.detector.detect(packet.frame)
        tracked_objects = self.tracker.update(
            detections=detections,
            frame=packet.frame,
            frame_time_seconds=packet.timestamp_seconds,
            source_name=packet.source_name,
        )
        face_state = self.face_monitor.analyze(
            frame=packet.frame,
            tracked_objects=tracked_objects,
            timestamp_seconds=packet.timestamp_seconds,
        )
        events = self.event_engine.evaluate(
            tracked_objects=tracked_objects,
            face_state=face_state,
            timestamp_seconds=packet.timestamp_seconds,
        )
        assert self.current_session is not None
        session_state = self.current_session.consume(packet, events)
        score_result = session_state.score_result
        annotated_frame = self.exporter.draw_overlay(
            frame=packet.frame.copy(),
            tracked_objects=tracked_objects,
            face_state=face_state,
            events=events,
            score_result=score_result,
        )
        self.exporter.log_events(packet.frame_index, tracked_objects, events)
        return FrameAnalysis(
            packet=packet,
            tracked_objects=tracked_objects,
            face_state=face_state,
            events=events,
            session_state=session_state,
            score_result=score_result,
            annotated_frame=annotated_frame,
        )

    def drain_completed_reports(self) -> List[SessionReport]:
        reports = list(self._completed_reports)
        self._completed_reports.clear()
        return reports

    def finalize_run(self, final_timestamp_seconds: float = 0.0) -> BatchReport:
        self._complete_current_source(final_timestamp_seconds)
        batch_report = self.batch_aggregator.build_report()
        exported_report = self.exporter.export_batch_report(batch_report, self.output_directory)
        self.face_monitor.close()
        return exported_report

    def _ensure_source_session(self, source_name: str) -> None:
        if self.current_source_name == source_name and self.current_session is not None:
            return

        self._complete_current_source(0.0)
        self.current_source_name = source_name
        self.current_session = SessionAggregator(source_name=source_name, scoring_engine=self.scoring)
        self.tracker.reset(source_name)
        self.face_monitor.reset()
        self.event_engine.reset()

    def _complete_current_source(self, final_timestamp_seconds: float) -> None:
        if self.current_session is None or self.current_source_name is None:
            return

        report = self.current_session.finalize(final_timestamp_seconds)
        report = self.exporter.export_session_report(report, self.output_directory)
        self.batch_aggregator.add_session_report(report)
        self._completed_reports.append(report)
        self.current_session = None
        self.current_source_name = None
