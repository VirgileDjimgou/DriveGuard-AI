from __future__ import annotations

from fastapi import FastAPI

from driver_monitoring.contracts import AnalyzeBatchRequestDto, AnalyzeVideoRequestDto, BatchReportDto
from driver_monitoring.core import analyze_batch, analyze_video


app = FastAPI(title="DriveGuard AI Local API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze/video", response_model=BatchReportDto)
def analyze_video_endpoint(request: AnalyzeVideoRequestDto) -> BatchReportDto:
    result = analyze_video(request.video_path, request.config_path)
    return result.batch_report_dto


@app.post("/analyze/batch", response_model=BatchReportDto)
def analyze_batch_endpoint(request: AnalyzeBatchRequestDto) -> BatchReportDto:
    result = analyze_batch(request.video_paths, request.config_path)
    return result.batch_report_dto
