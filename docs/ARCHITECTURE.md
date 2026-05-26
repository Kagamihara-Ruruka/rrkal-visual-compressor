# Architecture

## Boundary

This repository owns the compression and export engine. It does not own UI state, RRKAL dataset discovery, or runtime-specific rendering.

```text
Input data
  -> Analyzer
  -> Compressor
  -> VisualModel
  -> Exporter
```

## Main Concepts

### Analyzer

Inspects input data and records basic properties:

- row count
- value ranges
- sampling regularity
- missing values
- candidate methods

The MVP analyzer only needs time series support.

The current analyzer emits a `TimeSeriesProfile` with sample count, x/y ranges,
step statistics, uniform-sampling detection, and non-finite counts. This profile
is attached to CLI metrics and `.vizasset` manifests so later agents can make
strategy decisions without re-reading raw data.

### Cleaning And Residuals

Cleaning is modeled as a reversible lineage step:

```text
raw series -> cleaned main series
raw series - cleaned main series -> residual layer candidate
```

The first cleaning operators are moving-average smoothing and global sigma
clipping. They do not mutate the raw series. A residual analyzer classifies the
remaining layer as sparse outliers, Fourier-friendly residual, statistical
noise, or no meaningful residual. This keeps "noise removal" from becoming data
loss by default.

Residual storage follows that classification:

- sparse outliers are stored as sparse `(index, x, delta_y)` points.
- Fourier-friendly residuals are stored as a secondary Fourier layer.
- statistical noise is summarized unless the caller explicitly asks to store it.

### Compressor

Transforms data into a compact model.

Initial compressors:

- `RDPCompressor`: keeps visually important polyline points.
- `FourierCompressor`: keeps high-energy frequency coefficients.

Future compressors:

- spline
- wavelet
- contour
- cluster hull
- Bezier fitting

### VisualModel

The stable intermediate representation between compression and export.

It should carry:

- model type
- input summary
- model parameters or external parameter files
- style defaults
- reconstruction hints
- metrics

It should not require Qt, Matplotlib, or RRKAL.

### Exporter

Exports a `VisualModel` into target artifacts:

- SVG
- SVGZ
- PNG preview
- `demo.py`
- `metrics.json`
- package folder

### `.vizasset`

The package folder is the first stable handoff contract for RRKAL and the
editor. It stores compact reconstruction data and generated previews, not raw
source data.

```text
model.vizretain/
  asset.json
  model.npz
  preview.svg
  metrics.json
  demo.py
```

`asset.json` records schema version, source summary, method metadata, metrics,
file sizes, file checksums, and lineage notes. `model.npz` stores compact model
parameters such as RDP points, Fourier coefficients, and optional channel band
points.

The package family has profile suffixes:

- `.vizretain`: residual-retaining package. Keeps sparse residual or Fourier
  residual layers when the build produces them.
- `.vizclean`: cleaned-main package. Drops residual layers from the package even
  if the build report computed them.
- `.vizasset`: neutral name for compatibility and manual workflows.

The package module can read this back into renderable arrays:

- `reconstruct_fourier(package, samples=...)`
- `reconstruct_channel(package, samples=...)`

The current domain reconstruction uses `linspace_from_min_max`, which is correct
for uniformly sampled time series and acceptable for the first editor handoff.
For irregular time axes, `model.npz` stores the original x-domain values and the
manifest marks `x_domain_mode = stored_x`. This costs more bytes but preserves
the sampling geometry needed by editor and RRKAL consumers.

## Export Modes

### Pure SVG

Best compatibility. Stores paths/shapes directly.

### Hybrid SVG

Stores heavy data layers as raster images while preserving axes, annotations, and labels as vector elements.

### Model-backed SVG

Stores compressed parameters in metadata or script. This can be much smaller but may not work in design tools.

## Sweet Spot

The project should benchmark break-even points instead of claiming universal superiority.

```text
model_size + overhead < direct_svg_size_at_same_error
```

The useful output is a curve:

```text
file size vs fidelity
```

not a single magic threshold.

The `bench` command is the first implementation of this idea. It compares:

```text
direct SVG bytes
  vs
model-backed .vizasset bytes
```

for a synthetic sample-size sweep. This keeps the Big-O discussion measurable:
direct SVG grows with sampled point count, while the model-backed package should
mostly grow with model parameters, fixed preview resolution, and metadata.
The report also includes the first observed sample count where the package is
smaller than direct SVG.
