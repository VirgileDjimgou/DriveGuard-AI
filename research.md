# Research

## Scope of this phase

Goal: finish phase 2 by formalizing the engine as a real core inference layer without removing the existing GUIs.

## Current state before implementation

The project already supports:

- GUI execution
- CLI execution
- local FastAPI execution
- reusable headless runner

So the engine is already operational without Tkinter.

## Remaining phase 2 gap

What is still missing is not raw functionality but structure:

- no explicit `core inference` facade exists
- CLI and API still assemble pipeline configuration themselves
- JSON responses are built ad hoc with `asdict`
- there is no stable backend-grade response contract

## Implementation direction

To truly complete phase 2 without removing the GUIs, the project should gain:

1. a dedicated core module exposing:
   - `analyze_video(path)`
   - `analyze_batch(paths)`
   - `analyze_webcam(device)`
2. stable request/response contracts for API/backend usage
3. a single orchestration path reused by CLI and API

This keeps:

- the existing GUI for quick manual testing
- the lightweight API test GUI

while making the engine cleaner and easier to reuse in a future backend service.
