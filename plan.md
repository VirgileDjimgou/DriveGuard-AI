# Plan

## Goal

Add a real seatbelt detection model without losing the current generic object detection pipeline.

Target outcome:

- keep the current COCO detector for generic objects
- add a second YOLO detector specialized for seatbelt detection
- normalize seatbelt detections into stable internal labels
- activate real `NO_SEATBELT` and seatbelt-present logic

## Architecture overview

Introduce an additive multi-detector architecture.

Proposed flow:

1. The primary YOLO detector continues producing generic detections.
2. A secondary YOLO detector runs only for seatbelt-specific labels.
3. The detector layer merges both result sets into one normalized detection stream.
4. The tracker and event engine continue to operate on normalized labels.
5. The seatbelt rule becomes active only when the seatbelt model is loaded.

## Technical approach

### 1. Extend the detector layer

Add support for:

- a primary model path
- an optional seatbelt model path
- merged inference results
- label normalization for specialized seatbelt classes

Example:

```python
detections = primary.detect(frame)
if seatbelt_detector is not None:
    detections.extend(seatbelt_detector.detect(frame))
```

### 2. Normalize seatbelt labels

The specialized model may expose labels such as:

- `seatbelt`
- `with_seatbelt`
- `without_seatbelt`

These should be mapped to stable internal labels such as:

- `seatbelt_present`
- `seatbelt_missing`

### 3. Update event logic

The event engine should support both:

- explicit missing-seatbelt detections
- absence-based seatbelt timeout only when the model supports positive seatbelt labels

Example:

```python
if "seatbelt_missing" in labels:
    emit("NO_SEATBELT")
elif supports_positive_only and not seatbelt_present_for_long_enough:
    emit("NO_SEATBELT")
```

### 4. Add model-path resolution and bootstrap

The repository should resolve a local seatbelt model path if present and optionally use a downloaded artifact placed in project assets.

### 5. Keep the rest of the pipeline stable

Tracker, face monitor, reporting, GUI, and exports should continue to work without a structural rewrite.

## Source-code impact

Expected files to update:

- `driver_monitoring/detector.py`
- `driver_monitoring/event_engine.py`
- `driver_monitoring/pipeline.py`
- `README.md`

Possible small updates:

- `driver_monitoring/gui.py`
- `research.md`

Expected new assets:

- `driver_monitoring/assets/seatbelt_best.pt`

## Risks and constraints

- the external seatbelt model may use unexpected label names
- specialized model inference will add runtime cost
- event logic must not emit `NO_SEATBELT` when the seatbelt model is unavailable
- generic detections and seatbelt detections must coexist without breaking tracking

## Implementation order

### Phase 1

- [x] Download or register a real seatbelt model artifact
- [x] Inspect and normalize the model's output labels
- [x] Add optional seatbelt model-path resolution

### Phase 2

- [x] Extend the detector layer to support a secondary seatbelt model
- [x] Merge generic and specialized detections into one stream
- [x] Preserve current detector compatibility when the seatbelt model is absent

### Phase 3

- [x] Update event logic to support normalized seatbelt labels
- [x] Activate real `NO_SEATBELT` behavior
- [x] Keep seatbelt behavior disabled when no specialized model is available

### Phase 4

- [x] Verify the pipeline initializes with both models
- [x] Verify the pipeline still initializes with only the COCO model
- [x] Document seatbelt model setup in the README

### Phase 5

- [x] Run Python compilation
- [x] Smoke-test merged detector behavior
- [x] Update this checklist after implementation

## Status

Implementation complete.
