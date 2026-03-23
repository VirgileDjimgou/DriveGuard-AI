# Research

## Scope reviewed

Files reviewed in the active application code:

- `yolo.py`
- `driver_monitoring/detector.py`
- `driver_monitoring/video_source.py`
- `driver_monitoring/tracker.py`
- `driver_monitoring/face_monitor.py`
- `driver_monitoring/event_engine.py`
- `driver_monitoring/scoring.py`
- `driver_monitoring/export.py`
- `driver_monitoring/pipeline.py`
- `driver_monitoring/gui.py`
- `README.md`

Non-application files also present:

- `yolo.ipynb`
- model weights in `yolov8n.pt` and `yolo-Weights/yolov8n.pt`
- IDE metadata in `.idea/`
- cached bytecode in `__pycache__/`

## System overview

The project is currently a desktop Python prototype for driver monitoring. It combines:

- YOLOv8 object detection
- DeepSORT object tracking
- MediaPipe face landmark analysis
- a Tkinter desktop GUI
- simple rule-based event detection

The application supports three acquisition modes:

- webcam
- single local video file
- batch processing over multiple local video files

The current user entry point is `yolo.py`, which launches `DriverMonitoringApp` from `driver_monitoring/gui.py`.

## End-to-end runtime flow

### GUI flow

`DriverMonitoringApp` builds a Tkinter interface with:

- source mode selection
- file chooser for video or batch mode
- start/stop controls
- live preview panel
- status, score, and event labels

When the user starts analysis:

1. `PipelineConfig` is built from the selected mode.
2. A background thread starts `_run_analysis_loop`.
3. `DriverMonitoringPipeline` is instantiated.
4. A `BaseVideoSource` is created with `create_video_source`.
5. Frames are read in a loop and each frame is passed to `pipeline.process_packet`.
6. The resulting annotated frame and metadata are pushed back to the Tkinter main thread via `root.after`.

### Frame processing flow

`DriverMonitoringPipeline.process_packet` currently does:

1. YOLO detection via `YoloDetector.detect`
2. DeepSORT tracking via `Tracker.update`
3. face analysis via `FaceMonitor.analyze`
4. event generation via `EventEngine.evaluate`
5. score computation via `ScoringEngine.calculate`
6. overlay rendering via `ResultExporter.draw_overlay`
7. console logging via `ResultExporter.log_events`

The return type is `FrameAnalysis`, which contains the raw packet, tracked objects, face state, current frame events, current score result, and the annotated frame.

## Current functionality present

### Video source support

Implemented in `driver_monitoring/video_source.py`:

- webcam capture
- single file video capture
- sequential batch traversal over multiple files
- timestamp generation based on frame index and capture FPS

### Object detection

Implemented in `driver_monitoring/detector.py`:

- YOLOv8 model loading from local weights
- confidence threshold filtering
- class name lookup from the model
- bounding box extraction

### Object tracking

Implemented in `driver_monitoring/tracker.py`:

- DeepSORT integration
- persistent track IDs within a source
- duration accumulation per track
- automatic tracker reset when the source name changes

### Driver analysis

Implemented in `driver_monitoring/face_monitor.py`:

- face detection and landmarks using MediaPipe Face Landmarker Tasks API
- head orientation estimation
- simplified gaze classification based on head orientation
- eye state estimation with EAR-like ratio
- mouth opening ratio
- off-road duration, eyes-closed duration, yawning duration
- face bounding box derivation from landmarks

### Event logic

Implemented in `driver_monitoring/event_engine.py`:

- `PHONE_NEAR_FACE`
- `PHONE_USE`
- `PHONE_VISIBLE`
- `PHONE_DETECTED_SHORT`
- `DISTRACTION`
- `DROWSINESS`
- `YAWNING`
- `SHARP_OBJECT_DETECTED`
- `NO_SEATBELT` logic is scaffolded but effectively inactive with the current COCO model because seatbelt labels are not available

### Scoring

Implemented in `driver_monitoring/scoring.py`:

- per-frame score calculation starting from 100
- penalty aggregation by event type

### Rendering and logs

Implemented in `driver_monitoring/export.py`:

- overlays for tracked objects
- overlays for head/gaze/eye/yawn state
- display of current frame score
- console output per detected tracked object and event

## Important limitations of the current system

### The score is not session-level

`ScoringEngine.calculate` only sees the events from the current frame. The returned score is therefore a frame snapshot, not a clip score, session score, or batch score.

### No event history exists

The system does not persist events across frames. If the same event is emitted over 50 frames, there is no deduplicated incident timeline, no first seen / last seen timestamps, and no incident count.

### No final report exists

There is currently:

- no per-video summary
- no per-batch summary
- no export artifact
- no JSON output
- no CSV output

### Batch mode is only a source iterator

Batch mode currently just streams clips one after another into the same GUI preview. There is no batch report and no final list of processed files with their results.

## Edge cases and behavioral details

### Source changes

`Tracker` resets when `source_name` changes. This avoids reusing object IDs across files.

### Variable FPS

Frame timestamps are based on `frame_index / fps`. If a file reports FPS correctly, durations are deterministic. If FPS is unavailable, `CaptureVideoSource` falls back to 30 FPS.

### Face not detected

If MediaPipe returns no face:

- `driver_present` falls back to whether a YOLO `person` exists
- face durations are reset
- all face-derived values become `None` or `False`

### Seatbelt logic with the current model

The current default YOLO model is standard COCO `yolov8n`. It does not expose a seatbelt class. The code accounts for this by disabling seatbelt-missing scoring unless seatbelt labels are present in the model classes.

### Event duplication

The engine emits events frame by frame. A sustained distraction can therefore appear as repeated identical events on consecutive frames. This is fine for a low-level signal stream but not for incident history or scoring.

## Bugs and weaknesses identified

### Cross-clip state leakage in face analysis

`FaceMonitor` keeps `_state_started_at` across calls. It does not reset when the video source changes. In batch mode, if a clip ends while the driver is off-road or yawning, the next clip starts with stale state timestamps until a reset condition occurs. Because timestamps restart from zero in each clip, this can lead to state carry-over and inconsistent durations.

### Cross-clip state leakage in event engine

`EventEngine` keeps:

- `_phone_near_face_started_at`
- `_seatbelt_missing_started_at`

These are not reset on source changes. In batch mode, a new clip can inherit prior per-track or per-session temporal state.

### Track IDs may collide across clips while event state persists

`Tracker` resets per source and restarts track IDs. Because `EventEngine` does not reset on source changes, a new clip can reuse the same `track_id` values while old phone-near-face state still exists. This can cause false durations on `PHONE_USE`.

### Score is misleading in the GUI

The GUI label says `Driver score`, but it shows only the current frame score. This is not the cumulative clip score a user would expect from product language like driver scoring.

### No source-level completion object

The pipeline exposes only per-frame analysis. There is no source/session abstraction. This makes it impossible to reliably implement:

- final clip summaries
- batch rollups
- export artifacts
- session-level score accumulation

### No cancellation handshake for an active analysis result flush

Stopping the analysis sets a thread event, but there is no final partial session summary generation. A stopped run simply terminates the loop and updates the status label.

### GUI thread safety is acceptable but minimal

Tk updates happen through `root.after`, which is correct. However:

- final result handling is minimal
- there is no disable/enable cycle on controls while processing
- batch completion has no dedicated UI state

### Export system does not exist despite module name

`ResultExporter` only draws overlays and prints to stdout. It does not export artifacts to disk.

## Notifications analysis

No notification subsystem exists in this repository.

Observed mechanisms that could be mistaken for notifications:

- Tkinter status labels
- Tkinter message boxes for errors or missing source selection
- console logging from `ResultExporter.log_events`

There is no:

- notification queue
- notification service
- pub/sub flow
- retry mechanism
- persistence of user-facing notifications

Therefore there is no notification flow to document beyond simple local UI updates and message boxes.

## Task scheduling analysis

No task scheduling subsystem exists in this repository.

What does exist:

- a single background analysis thread launched from the GUI
- a loop that reads frames sequentially until stopped or exhausted
- UI callbacks posted back into the Tkinter event loop with `root.after`

There is no:

- job scheduler
- persisted task state machine
- retry scheduler
- queue-backed worker system
- cancel/resume workflow

The closest equivalent to task scheduling bugs in this repository is lifecycle control of analysis sessions. The critical flaws are:

- no explicit source/session object
- no reset hooks for stateful components on source transitions
- stop action does not produce a partial summary
- batch processing has no per-clip completion event

## Pagination analysis

No list endpoint exists in this repository.

Therefore:

- there is no offset pagination
- there is no cursor pagination
- there is no API list flow to migrate

## Conclusions relevant to step 6

The next feature should not be implemented as another per-frame patch. The project now needs a session/reporting layer.

The missing product layer should introduce:

- a session abstraction per source video
- persistent in-memory event history during a run
- deduped incidents instead of frame-by-frame duplicates
- cumulative score over the session
- final reports per source
- batch summaries across multiple sources
- JSON and CSV exports

Without that layer, the GUI and scoring remain demo-oriented rather than product-oriented.

## Additional research for real seatbelt model integration

### Current seatbelt support status

The repository does not currently include a real seatbelt detection model.

The existing `NO_SEATBELT` rule in `driver_monitoring/event_engine.py` is only a placeholder. It can trigger only if the loaded detection model exposes one of these labels:

- `seat belt`
- `seatbelt`
- `safety belt`

The default detector is still COCO `yolov8n`, which does not expose such classes. Therefore the current seatbelt logic is inactive by design.

### Integration options considered

#### Option 1: Replace the main COCO model with a seatbelt-specific model

This would improve seatbelt detection but would break or severely reduce all other current behaviors:

- phone detection
- person detection
- knife detection
- generic cabin object detection

This is not compatible with the current product direction.

#### Option 2: Add a second specialized detector only for seatbelt-related classes

This is the most coherent option for the current codebase because:

- the rest of the pipeline already expects YOLO-style detections
- no tracker rewrite is required
- event logic can remain object-label based
- seatbelt support becomes additive rather than destructive

This is the preferred architecture.

### External model research

I reviewed publicly available candidate sources for seatbelt detection:

- `HayaAbdullahM/Seat-Belt-Detection` on GitHub: useful as reference and dataset pointer, but it does not publish a ready release artifact on the repository page reviewed. It is more useful as training/reference material than as a drop-in runtime dependency.
- Microsoft HAMS seatbelt docs: demonstrates a dedicated seatbelt pipeline, but it relies on a different stack and model format (`seatbelt_model.pth`) and is less aligned with the current YOLO pipeline.
- `huzi0906/seatbelt-handsOnWheel-detection` on Hugging Face Spaces: exposes a YOLO-compatible `weights/best.pt` artifact and uses `from ultralytics import YOLO`, which makes it directly compatible with the current detector design.

### Preferred model choice

The most integration-friendly candidate is the YOLO model artifact published in:

- Hugging Face Space `huzi0906/seatbelt-handsOnWheel-detection`

Reasons:

- direct YOLO `.pt` artifact
- inference pattern matches the project's existing Ultralytics usage
- low friction to merge into the current multi-detector flow
- no need to rewrite event logic around a non-YOLO classifier

### Expected integration impact

To support a real seatbelt model safely, the code needs:

- support for multiple YOLO detectors in `detector.py`
- explicit mapping from specialized seatbelt classes to normalized labels understood by the event engine
- optional model-path resolution for the seatbelt weights
- session-safe event logic for `NO_SEATBELT`

### Seatbelt-specific risks

- the external model may use label names different from the current placeholder labels
- some seatbelt models detect `with_seatbelt` and `without_seatbelt` rather than `seatbelt`
- `NO_SEATBELT` should not be inferred from silence unless the specialized seatbelt model is active
- false positives can occur if the specialized model was trained on different camera angles than cabin-facing trucking footage

### Implementation direction

The safest implementation is:

1. keep the current COCO model as the primary detector
2. add an optional secondary seatbelt model
3. normalize its classes into stable internal labels
4. update event logic to support both:
   - positive seatbelt presence
   - explicit no-seatbelt classes when available
