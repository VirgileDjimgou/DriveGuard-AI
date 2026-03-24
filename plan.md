# Plan

## Goal

Complete phase 2 by formalizing a core inference layer and stable JSON/backend contracts, while keeping both Tkinter GUIs available for rapid testing.

## Technical approach

1. Add a `core.py` facade exposing high-level analysis functions.
2. Add `contracts.py` with stable Pydantic response models.
3. Refactor CLI and local API to use the same core facade.
4. Keep the existing GUI layers untouched as presentation/testing tools.

## Implementation order

### Phase 1

- [x] Add core inference facade
- [x] Expose analyze functions for video, batch, and webcam

### Phase 2

- [x] Add backend-grade contracts
- [x] Add conversion from internal reports to response models

### Phase 3

- [x] Refactor CLI to use core inference
- [x] Refactor local API to use core inference

### Phase 4

- [x] Update README
- [x] Run Python compilation
- [x] Smoke-test CLI and API imports

## Status

Implementation complete.
