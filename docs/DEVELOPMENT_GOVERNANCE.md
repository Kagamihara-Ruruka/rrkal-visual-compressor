# Development Governance

This repository follows RRKAL-style development discipline: keep the core model
small, keep source truth separate from projections, and make every feature
testable through documented commands.

## Source Of Truth

- Raw input data is read-only.
- Compressed visual models are the source of reconstruction.
- SVG, demo scripts, PNGs, and editor views are exports, not the canonical data.
- Future `.vizasset` packages must keep source metadata, processing parameters,
  fidelity metrics, and lineage together.

## MVP Boundary

The current mainline is:

```text
time series -> compact visual model -> SVG/demo.py/metrics
```

Features belong on the mainline only if they improve this flow. Longer-term
ideas such as 2D shape fields, void/material assets, 3D implicit assets, Unreal
projection, or editor UI should stay in docs, contracts, or isolated stubs until
they have a CLI path and tests.

## Project Boundaries

- This repo owns compression algorithms, visual model contracts, metrics, and
  export preparation.
- The editor repo owns interaction, styling, annotation, and Photoshop-like UI.
- RRKAL owns asset registry, source manifests, install state, and broader data
  lineage.
- Runtime engines are consumers of exported packages, not owners of the model.

## Engineering Rules

- Every new user-facing feature needs a CLI route, tests, and metrics output.
- Do not add hidden one-off scripts for core behavior.
- Do not commit generated outputs, private datasets, caches, or local runtime
  artifacts.
- Prefer small, typed modules over sample-code adoption.
- Update docs when a change affects usage, architecture, roadmap, or agent
  handoff.
- Treat compression claims as measurable hypotheses: report sample count,
  parameter count, error, and coverage instead of relying on theory alone.

## Research Gate

Before promoting a research idea into implementation, answer:

1. What MVP segment does it serve?
2. Which CLI command exercises it?
3. Which test proves it works?
4. Which metrics show whether it wins or loses?
5. If removed, would the current MVP break?

If the answer to the last question is "no", keep it behind a documented
research boundary until the mainline needs it.
