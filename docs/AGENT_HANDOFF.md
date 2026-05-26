# Agent Handoff

## Mission

Build a small, testable visual compression engine before expanding scope.

## Hard Boundaries

- Do not add Qt here.
- Do not build the visual editor here.
- Do not integrate Unreal here.
- Do not claim universal compression.
- Keep this package importable by RRKAL and the editor.

## First Task

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
