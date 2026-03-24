# Research

## Scope of this phase

Goal: prepare the inference engine to run without Tkinter, through a local CLI or a local API.

## Current state before implementation

The core inference logic is already mostly independent from the desktop UI:

- `pipeline.py` contains the modular analysis chain
- `reporting.py` already produces source and batch reports
- `video_source.py` already abstracts webcam, single-video, and batch inputs

The main remaining coupling to Tkinter was the runtime loop itself, implemented inside `gui.py`.

## Key observation

The project does not need a full architectural rewrite to become headless. It only needs:

- a reusable runner loop outside the GUI
- a CLI entry point
- a local API entry point

## Constraints identified

- the GUI should remain usable
- the same pipeline should be reused to avoid drift
- reports and exports must remain identical between GUI, CLI, and API execution
- configuration should still come from `config.toml`

## Implementation direction

The cleanest solution is:

1. extract a headless execution loop into a dedicated runner module
2. keep `gui.py` as a presentation layer around the same pipeline
3. add:
   - `driver_monitoring/cli.py`
   - `driver_monitoring/api.py`

This provides both:

- immediate local automation through the CLI
- a first service-shaped API surface for later backend migration
