from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from driver_monitoring.core import analyze_batch, analyze_video, analyze_webcam


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DriveGuard AI without the Tkinter GUI.")
    parser.add_argument("--config", default="config.toml", help="Path to the TOML configuration file.")

    subparsers = parser.add_subparsers(dest="mode", required=True)

    webcam_parser = subparsers.add_parser("webcam", help="Analyze a webcam stream.")
    webcam_parser.add_argument("--device", type=int, default=0, help="Webcam device index.")

    video_parser = subparsers.add_parser("video", help="Analyze a single video file.")
    video_parser.add_argument("--source", required=True, help="Path to the input video.")

    batch_parser = subparsers.add_parser("batch", help="Analyze multiple video files.")
    batch_parser.add_argument("--sources", nargs="+", required=True, help="Paths to the input videos.")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "webcam":
        result = analyze_webcam(device=args.device, config_path=args.config)
    elif args.mode == "video":
        result = analyze_video(video_path=args.source, config_path=args.config)
    else:
        result = analyze_batch(video_paths=args.sources, config_path=args.config)

    batch_report = result.batch_report_dto
    print(f"Sources processed: {batch_report.total_sources}")
    print(f"Total incidents: {batch_report.total_incidents}")
    print(f"Average score: {batch_report.average_score:.1f}")
    print(f"Exports: {batch_report.output_directory}")
    for report in batch_report.session_reports:
        source_name = Path(report.source_name).name if report.source_name != "0" else "webcam_0"
        print(
            f"- {source_name}: score={report.score_result.score}, "
            f"incidents={len(report.incidents)}, duration={report.duration_seconds:.1f}s"
        )


if __name__ == "__main__":
    main()
