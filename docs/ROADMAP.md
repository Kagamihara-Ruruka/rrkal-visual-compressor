# Roadmap

This project should grow from a narrow, testable compression engine into a geometry-aware visual modeling system. The first rule is scope control: prove one class of data before adding another.

## Core Thesis

Traditional SVG couples visual complexity to raw sample count:

```text
N samples -> O(N) path/circle output
```

This project should couple visual complexity to model complexity:

```text
N samples -> O(A + K + T) visual model
```

Where:

- `A`: anchors such as center, focus points, or skeleton points.
- `K`: function parameters such as Fourier coefficients or spline knots.
- `T`: topology metadata such as closed/open, holes, components, and boundaries.

SVG is an export target. The compressed visual model is the source of truth.

## Phase 0: Proof Migration

Goal: move the existing proof into tested library modules.

Tasks:

- Move RDP, Fourier reconstruction, SVG path writing, and metrics into `src/vizcompress/`.
- Add synthetic time-series fixture generation.
- Add time-series analyzer profiles for ranges, step regularity, and non-finite counts.
- Add unit tests for import, RDP, Fourier, metrics, and SVG export.
- Keep the implementation CPU/NumPy-first.

Deliverables:

```text
src/vizcompress/compressors.py
src/vizcompress/metrics.py
src/vizcompress/exporters.py
tests/test_timeseries_compression.py
```

Definition of done:

- `py -m pytest` passes.
- CLI can generate SVG and metrics from synthetic data.
- No GUI dependencies.

## Phase 1: Time Series MVP

Goal: make the first useful compressor for finite time-series data.

Supported input:

```text
CSV(time, value)
```

Methods:

- RDP simplified path.
- Fourier center function.
- Fixed display-resolution SVG sampling.
- `demo.py` export that can reproduce the generated model.

Metrics:

- RMSE
- MAE
- max absolute error
- R2
- compression ratio by count
- generated file sizes

Success criteria:

```text
1,000,000 samples
  -> compact visual model
  -> SVG opens in a browser
  -> demo.py reproduces the model
  -> metrics report compression ratio and error
```

## Phase 2: Center Function + Channel Model

Goal: move beyond a single reconstructed line.

Concept:

```text
center(t) = fitted function
band(t) = fitted uncertainty / residual envelope
valid range = center(t) +/- k * band(t)
```

Initial implementation:

- `ChannelModel` wrapping a Fourier center function.
- residual calculation.
- `global_std` band.
- `rolling_std` band.
- RDP simplification for the band curve.
- `rolling_quantile` band remains deferred.

SVG output:

- center path
- translucent channel
- optional outlier markers

Metrics:

- coverage ratio
- outlier count
- mean band width
- max band width
- center RMSE
- channel model size

This phase is important because it encodes visual fidelity as a range, not just as a center line.

## Phase 2.5: Video-First Functional Encoding Research

Goal: prove that temporal axes are just another function axis in the same compression
pipeline, not a separate engine.

Model:

```text
V(t, x, y) ≈ Σk c_k(t) · φk(x, y) + Î(x, y)
```

where:

- `φk` are spatial modes (POD / low-rank approximation),
- `c_k(t)` are one-dimensional temporal coefficient functions (Fourier),
- `Î` is the mean frame.

Prototype tasks:

- Build `VideoCube` for structured frame sequences.
- SVD/POD decomposition by frame axis.
- Temporal Fourier for each coefficient channel.
- Rendering-reconstruction on demand for target FPS/viewport sample count.
- Evidence report: raw bytes vs function bytes, video RMSE/MAE/max error, size break-even.

Definition of done:

- Reconstruction at the original frame count matches synthetic low-rank test films with
  R2 >= 0.99.
- Up/down sampling from the model works (e.g., reconstruct 240 fps from 120-source
  samples).
- Reported `size_ratio` and `source-back` evidence are explicit and reproducible.

This phase is experimental and does not change package format yet; it should produce
research-level checkpoints and scripts first.

### Phase 2.6: Locality Defect Research (Defensible)

Goal: address global basis locality risk with evidence, not opinion.

Current checkpoint:

- `src/vizcompress/research.py` supports jump detection, piecewise Fourier,
  and locality leakage metrics.
- `tests/test_research.py` verifies finite reconstruction and compares
  jump-neighborhood leakage for step-like data.
- `docs/RESEARCH_NOTES.md` documents the hard risks and interpretation protocol.

Acceptance criteria:

- local leakage ratio for piecewise path should not be worse than global Fourier
  on discontinuity-heavy signals under the same term budget.
- every future model variant must declare its locality behavior in benchmark rows.

### Phase 2.7: Defensible Baseline Expansion

Goal: add two failure-focused baselines before broader production claims.

Tasks:

- Add irregular-x Fourier baseline via uniform re-parameterization (`compress_fourier_with_uniform_param`).
- Add local polynomial baseline for locality stress (`compress_piecewise_polynomial`).
- Add correlated multichannel baseline (`compress_multichannel_fourier_pca`).
- Add polyline simplification stress as a pre-pass (RDP/angle/curvature pruning) to model DPI-aware sampling budgets.
- Extend benchmark evidence with:
  - locality leakage metrics
  - x-domain max error
  - residual payload ratio
- Add a DPI-gating rule in research: if the requested output is `W×H`, clamp target samples to a multiple of visible pixel span.

Definition of done:

- Each baseline has at least one reproducible benchmark row.
- No single baseline is considered “better” unless it wins both:
  - error budget constraints
  - payload constraints

## Phase 2.8: Operational Hardening

Goal: make repeated local sessions reproducible and low-noise.

Tasks:

- Keep generated artifact directories out of commit history unless explicitly
  approved.
- Align project documentation with the actual workspace boundaries:
  - `L:\rrkal-visual-compressor` as the development workspace.
  - `Notion Agents討論區` as the non-product coordination forum.
  - `L:\AGENT_EXCHANGE` as archive/history reference only.
- Add a checkpoint-close flow that records unresolved recommendations and
  required follow-ups.

Definition of done:

- No generated artifacts are committed by default.
- The handoff process for this repo clearly records environment assumptions and
  next actions.
- At least one checkpoint update includes a concrete next-step item for another
  team.

## Phase 3: `.vizasset` Package Format

Goal: define the handoff contract between compressor, editor, and RRKAL.

Package shape:

```text
example.vizasset/
  asset.json
  model.json or model.npz
  preview.svg
  metrics.json
  demo.py
```

`asset.json` should include:

- source summary
- model type
- method parameters
- model parameter file references
- metrics summary
- export profiles
- RRKAL lineage hints

Definition of done:

- Package manifest read/write round trip.
- CLI can build a `.vizasset`.
- The package contains compact model parameters, preview, metrics, and demo.
- The package can be opened by a separate editor without reading raw data.

Current status:

- Minimal package writer exists.
- `asset.json` includes file hashes and lineage notes.
- `model.npz` stores RDP, Fourier, and optional channel compact parameters.
- Fourier and channel readback can reconstruct renderable arrays.
- Irregular time-domain reconstruction supports preserved x values and compressed
  linear-plus-delta encoding.
- Package verification exists for manifest/files/hash/model-array/reconstruction
  self-consistency.
- `video-bench` CLI and synthetic video sweep outputs are in progress for
  separable spatiotemporal function compression research.

Next package work:

- Add source-backed fidelity verification when original input is available.
- Emit review packets that record accepted error budgets and baseline comparison.
- Add schema fixtures so future agents can verify backward compatibility.

### Phase 3.1: Renderer Skin Asset Compatibility Notes

Goal: prepare the handoff path for RRKAL renderer/runtime consumers.

- Define how `.vizasset` manifest fields map to `RendererSkinAsset` expectations.
- Lock down `compatibility` schema and renderer-readiness flags.
- Identify required conversion layer between `review.json` / `verify` outputs and registry gate checks.

Current output:  
`docs/RENDERER_SKIN_ASSET_COMPATIBILITY_NOTES.zh-TW.md`

Completion criteria:

- Documented compatibility matrix from `.vizasset` fields to renderer/core assumptions.
- Explicit acceptance conditions (`schema_version`, `compatibility`, `files`, `review`) for bridge ingestion.
- Traceable open questions for RRKAL runtime implementation (e.g., native loader + render-state).

## Phase 4: 2D Curve And Shape Compression

Goal: support geometry-aware vectorization for 2D paths and closed contours.

Topology classification:

- `open_curve`
- `closed_curve`
- `multi_contour`

Methods:

- RDP for open and closed curves.
- parametric Fourier: `x(t), y(t)`.
- radial Fourier: `r(theta)` from a selected center.
- Bezier path fitting, if needed for SVG size reduction.

Center selectors:

- centroid
- area centroid
- geometric median
- bounding-box center
- Chebyshev center, if practical

Metrics:

- Chamfer distance
- Hausdorff distance
- area error
- closedness error
- self-intersection warnings

Definition of done:

- Closed contour can be compressed into radial Fourier and exported as SVG.
- Different center choices can be benchmarked.

## Phase 5: Anchor And Focus Models

Goal: use better coordinate systems to reduce model complexity.

Concept:

```text
single center -> radial distance
dual focus -> elliptic distance representation
multi-anchor -> distance field / skeleton-inspired representation
```

Initial dual-focus method:

- Use PCA to find the long axis.
- Place two foci along that axis.
- Encode boundary by distance features such as `d1 + d2` and `d1 - d2`.
- Fit the resulting functions with Fourier or spline models.

Use cases:

- elongated objects
- ellipse-like objects
- two-ended contours

Definition of done:

- Strategy benchmark can compare radial center vs dual-focus representation on synthetic elongated contours.

## Phase 6: Strategy Selector

Goal: let users specify a fidelity budget instead of choosing algorithms manually.

Input:

```text
target_error
target_format
priority = smallest | fastest | most_editable | most_compatible
```

Candidate methods:

- direct sampled SVG
- RDP
- Fourier center
- Fourier channel
- radial Fourier
- dual-focus model

Selection rule:

```text
choose the smallest model/export that satisfies the fidelity budget
```

Definition of done:

- CLI can run `--method auto`.
- Report explains why a method was selected.

Pre-work now available:

- `bench` can produce size/fidelity rows for direct SVG vs model-backed package.
- These rows are the data source for future automatic method selection.
- Residual analysis can mark cleaned residuals as sparse, Fourier-friendly, or
  statistical noise, which is an early strategy-selection primitive.

## Phase 7: Path Complexity Optimizer

Goal: reduce SVG size after model reconstruction.

Optimizations:

- decimal precision control
- relative path commands
- redundant point removal
- optional gzip/SVGZ
- Bezier fitting
- fixed display-resolution sampling

Definition of done:

- Export report separates model size from SVG realization size.

## Phase 8: Material / Void / Projection Research Line

Goal: document and prototype semantic geometry without blocking the MVP.

Initial proof should be 2D only:

```text
solid region
void region
-> exterior projection
-> void-only projection
-> compound SVG path
```

Concepts:

- material labels
- `void` as empty physical region
- region projection
- topology from solid/void composition

This is not part of the first production path. It is a research track for future functional assets.

## Phase 9: 3D Functional Asset Research Line

Deferred until 2D and `.vizasset` are stable.

Possible methods:

- SDF primitives
- CSG composition
- radial 3D: `r(theta, phi)`
- spherical harmonics
- base function plus residual detail
- mesh reconstruction through marching cubes

Non-goals for now:

- robust arbitrary mesh boolean
- full physics simulation
- Unreal runtime adapter
- neural field production pipeline

## Immediate Work Plan

Start with Phase 0 and Phase 1 only:

1. Port the proof script into library modules.
2. Add tests.
3. Add CLI generation for synthetic data.
4. Add CSV time-series input.
5. Add SVG, `demo.py`, and `metrics.json` export.
6. Push the first implementation branch.

Phase 2 has started with Fourier channel models. Keep the next work scoped to
metrics, package contracts, and strategy comparison before moving into 2D
geometry research.
