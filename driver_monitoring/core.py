from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from driver_monitoring.config import AppConfig, load_app_config
from driver_monitoring.contracts import BatchReportDto, batch_report_to_dto
from driver_monitoring.pipeline import PipelineConfig
from driver_monitoring.runner import RunResult, run_headless


@dataclass
class CoreAnalysisResult:
    run_result: RunResult
    batch_report_dto: BatchReportDto


def analyze_video(video_path: str, config_path: str = "config.toml") -> CoreAnalysisResult:
    app_config = load_app_config(config_path)
    pipeline_config = PipelineConfig.from_app_config(app_config, "video", video_path)
    pipeline_config.config_path = config_path
    run_result = run_headless(pipeline_config)
    return CoreAnalysisResult(
        run_result=run_result,
        batch_report_dto=batch_report_to_dto(run_result.batch_report),
    )


def analyze_batch(video_paths: Sequence[str], config_path: str = "config.toml") -> CoreAnalysisResult:
    app_config = load_app_config(config_path)
    pipeline_config = PipelineConfig.from_app_config(app_config, "batch", list(video_paths))
    pipeline_config.config_path = config_path
    run_result = run_headless(pipeline_config)
    return CoreAnalysisResult(
        run_result=run_result,
        batch_report_dto=batch_report_to_dto(run_result.batch_report),
    )


def analyze_webcam(device: int = 0, config_path: str = "config.toml") -> CoreAnalysisResult:
    app_config = load_app_config(config_path)
    pipeline_config = PipelineConfig.from_app_config(app_config, "webcam", device)
    pipeline_config.config_path = config_path
    run_result = run_headless(pipeline_config)
    return CoreAnalysisResult(
        run_result=run_result,
        batch_report_dto=batch_report_to_dto(run_result.batch_report),
    )
