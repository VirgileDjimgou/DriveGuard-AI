from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable, List, Optional

from driver_monitoring.pipeline import DriverMonitoringPipeline, FrameAnalysis, PipelineConfig
from driver_monitoring.reporting import BatchReport, SessionReport


@dataclass
class RunResult:
    session_reports: List[SessionReport]
    batch_report: BatchReport


def run_headless(
    config: PipelineConfig,
    on_frame: Optional[Callable[[FrameAnalysis], None]] = None,
    on_session_complete: Optional[Callable[[SessionReport], None]] = None,
    stop_event: Optional[Event] = None,
) -> RunResult:
    pipeline = DriverMonitoringPipeline(config)
    source = pipeline.create_source()
    session_reports: List[SessionReport] = []
    last_timestamp_seconds = 0.0

    try:
        source.open()
        while stop_event is None or not stop_event.is_set():
            packet = source.read()
            if packet is None:
                break

            last_timestamp_seconds = packet.timestamp_seconds
            analysis = pipeline.process_packet(packet)
            if on_frame is not None:
                on_frame(analysis)

            completed_reports = pipeline.drain_completed_reports()
            session_reports.extend(completed_reports)
            if on_session_complete is not None:
                for report in completed_reports:
                    on_session_complete(report)

        batch_report = pipeline.finalize_run(last_timestamp_seconds)
        completed_reports = pipeline.drain_completed_reports()
        session_reports.extend(completed_reports)
        if on_session_complete is not None:
            for report in completed_reports:
                on_session_complete(report)
        return RunResult(session_reports=session_reports, batch_report=batch_report)
    finally:
        source.close()
