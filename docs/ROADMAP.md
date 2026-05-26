# Roadmap

## Phase 0: Proof Migration

- Move the existing proof script into library modules.
- Add tests for RDP and Fourier reconstruction.
- Generate SVG and metrics from a synthetic time series.

## Phase 1: Time Series MVP

- CSV input with configurable x/y columns.
- RDP compression.
- Fourier compression.
- Auto benchmark mode.
- SVG export.
- `demo.py` export.
- `metrics.json` export.

Success criteria:

```text
1,000,000 samples
  -> compact visual model
  -> SVG opens in a browser
  -> demo.py reproduces the model
  -> metrics report compression ratio and error
```

## Phase 2: Package Format

- Define `.vizasset` folder layout.
- Store `asset.json`, model parameters, preview SVG, metrics, and demo script.
- Support load/save round trip.

## Phase 3: Additional 2D Methods

- Spline approximation.
- Wavelet approximation.
- Density contour for large scatter.
- Bezier path fitting.

## Phase 4: RRKAL Integration

- Treat `.vizasset` as a derived visual asset.
- Preserve source dataset UID, manifest reference, and lineage.
- Add CLI outputs that RRKAL can register.

## Deferred

- 3D implicit functions.
- Neural fields.
- Unreal projection.
- Live editor UI.
- Real-time streams.
