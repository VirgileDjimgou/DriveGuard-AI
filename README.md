# Real-Time Object Detection with YOLOv8 and OpenCV

This repository started as a simple YOLOv8 webcam demo and is now being refactored into a modular baseline for a future driver-monitoring and video-telematics system.

## Current architecture

- `driver_monitoring/video_source.py`: video capture and display
- `driver_monitoring/detector.py`: YOLO loading and object detection
- `driver_monitoring/tracker.py`: tracking interface placeholder
- `driver_monitoring/face_monitor.py`: face-state analysis placeholder
- `driver_monitoring/event_engine.py`: event generation rules
- `driver_monitoring/scoring.py`: score calculation
- `driver_monitoring/export.py`: overlay rendering and console export
- `driver_monitoring/pipeline.py`: orchestration of the full pipeline
- `driver_monitoring/reporting.py`: session history, cumulative scoring, and final reports
- `driver_monitoring/gui.py`: desktop GUI for webcam, single-video, and batch-video analysis

## Entry point

Run the application with:

```bash
python yolo.py
```

## Requirements

- Python 3.x
- OpenCV
- Ultralytics YOLOv8
- Pillow
- deep-sort-realtime
- mediapipe
- optional seatbelt YOLO weights in `driver_monitoring/assets/seatbelt_best.pt`

## Notes

- The project still works as a webcam-based object detector.
- The GUI now supports three modes: webcam, single video file, and batch clip analysis.
- Session reports are exported to `outputs/run_*` as JSON and CSV.
- If `driver_monitoring/assets/seatbelt_best.pt` is present, the app enables dedicated seatbelt detection alongside the generic COCO detector.
- The modular structure is intended to receive richer business rules and backend integration in later steps.
