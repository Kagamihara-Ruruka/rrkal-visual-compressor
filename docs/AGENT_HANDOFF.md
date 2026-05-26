# Agent Handoff

## Mission

Build a small, testable visual compression engine before expanding scope.

## Hard Boundaries

- Do not add Qt here.
- Do not build the visual editor here.
- Do not integrate Unreal here.
- Do not claim universal compression.
- Keep this package importable by RRKAL and the editor.

## Current Workspace Rule

- Develop in `K:\Codex\2026-05-26\qt-vispy\rrkal-visual-compressor`.
- Use `C:\Users\lyn59\Documents\Codex\2026-05-26\qt-vispy\rrkal-visual-compressor`
  as the local test copy.
- Push cloud-workspace commits to GitHub `origin/main`.

## Current Status

Implemented mainline:

- time-series analyzers and synthetic fixtures
- RDP and Fourier compressors
- Fourier channel model
- cleaning as layered modeling, not destructive deletion
- sparse residual layer and Fourier residual noise layer
- `.vizretain`, `.vizclean`, and neutral `.vizasset` package family
- package readback for Fourier, channel, sparse residual, and noise layers
- irregular x-domain handling with preserve, compressed, and auto policies
- benchmark matrix with per-kind summaries and recommendation labels
- `build`, `bench`, `recommend`, and `inspect` CLI commands

Current local verification command:

```powershell
py -m pytest -q
```

Latest known passing count: `27 passed`.

## Original First Task

Port `proof_vectorization.py` into:

```text
src/vizcompress/compressors.py
src/vizcompress/exporters.py
src/vizcompress/metrics.py
tests/test_timeseries_compression.py
```

## Definition Of Done For First PR

- `py -m pytest` passes.
- CLI can generate SVG and metrics from synthetic data.
- README quickstart works.
- No UI dependencies.

## Design Principle

The compressed model is the source of visual reconstruction. SVG is an export target, not the internal truth.

Residuals are not automatically discarded. A retained package keeps residual
layers when available; a clean package exports only the cleaned main signal.
