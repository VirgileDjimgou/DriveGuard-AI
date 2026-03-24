# Plan

## Goal

Prepare the inference engine to run without Tkinter through:

- a reusable headless runner
- a local CLI
- a local API

## Technical approach

1. Extract the execution loop from the GUI into a reusable runner.
2. Reuse the existing pipeline and reporting stack unchanged.
3. Add a CLI for webcam, single-video, and batch modes.
4. Add a minimal local FastAPI service with health and analysis endpoints.
5. Document how to use both entry points.

## Implementation order

### Phase 1

- [x] Add a headless runner around `DriverMonitoringPipeline`
- [x] Keep source/session finalization behavior identical to the GUI

### Phase 2

- [x] Add a CLI entry point
- [x] Support webcam, video, and batch usage

### Phase 3

- [x] Add a local API entry point
- [x] Expose health and analysis endpoints

### Phase 4

- [x] Update README with CLI and API usage
- [x] Run Python compilation
- [x] Smoke-test CLI and API imports

## Status

Implementation complete.
