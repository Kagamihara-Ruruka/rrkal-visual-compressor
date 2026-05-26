# RRKAL Visual Compressor

Traditional Chinese documentation is available in [README.zh-TW.md](README.zh-TW.md).

RRKAL Visual Compressor is a Python-first engine for turning large datasets into compact, reproducible visual models.

It is not a general charting library and it is not the editor UI. Its job is to compile data into an intermediate visual representation that can later be exported as SVG, PNG, `demo.py`, metrics, or an asset package consumed by RRKAL and editor tools.

## Core Idea

```text
large data
  -> analysis
  -> approximation / compression
  -> visual model IR
  -> SVG / demo.py / metrics / package
```

The first target is time series data:

```text
CSV(time, value)
  -> RDP / Fourier / spline approximation
  -> compact visual model
  -> SVG path
  -> reproducible demo.py
  -> metrics.json
```

## Why This Exists

Directly exporting large data into SVG is usually the wrong model:

```text
1,000,000 samples -> 1,000,000 SVG path points
```

This project explores the better model:

```text
1,000,000 samples -> compact model -> visual reconstruction
```

The goal is not lossless data archival. The goal is visual compression with measurable fidelity.

## MVP Scope

The first milestone should only support:

- time series input from CSV
- Ramer-Douglas-Peucker polyline simplification
- Fourier approximation
- simple SVG path export
- `demo.py` export
- `metrics.json` export
- benchmark reports comparing size, error, and compression ratio

Everything else is deferred.

## Non-Goals

- No Qt UI.
- No Photoshop-like editor.
- No Unreal integration in this repo.
- No universal file compression claim.
- No 3D function assets in the first milestone.
- No promise that every dataset compresses better than SVG.

## Relationship To Other Projects

```text
RRKAL
  source of truth for data assets, manifests, lineage, install registry

RRKAL Visual Compressor
  converts large data into compact visual models

RRKAL Visual Editor
  opens visual model packages and lets users style, annotate, and export them
```

## Repository Layout

```text
src/vizcompress/
  core.py          Visual model and package primitives
  metrics.py       Fidelity and compression metrics
  compressors.py   RDP and Fourier starter compressors
  exporters.py     SVG, demo.py, metrics exporters
  cli.py           CLI entrypoint

docs/
  ARCHITECTURE.md
  CONCEPTUAL_MODEL.md
  ROADMAP.md
  AGENT_HANDOFF.md
  DEVELOPMENT_GOVERNANCE.md
  *.zh-TW.md       Traditional Chinese versions
```

See [docs/DEVELOPMENT_GOVERNANCE.md](docs/DEVELOPMENT_GOVERNANCE.md) for the
RRKAL-inspired development rules used by agents working in this repository.
See [docs/CONCEPTUAL_MODEL.md](docs/CONCEPTUAL_MODEL.md) for the mathematical
boundary: representation is not compression, accepted packages must be
verifiable, and the project does not claim universal compression.

## Development

```powershell
py -m pip install -e .
py -m pytest
vizcompress --help
```

## First Working Command

Generate a synthetic time series, compress it with RDP and Fourier, then export SVG, `demo.py`, and `metrics.json`:

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --svg-samples 1200 --out smoke_outputs
```

Add `--direct-svg` when you want a traditional full-point SVG baseline in the
same output directory:

```powershell
py -m vizcompress.cli build --synthetic 100000 --direct-svg --fourier-terms 96 --out smoke_outputs
```

Synthetic fixtures include `smooth`, `spikes`, `steps`, `chirp`, `multiscale`,
`noisy`, and `irregular`:

```powershell
py -m vizcompress.cli build --synthetic 100000 --synthetic-kind spikes --channel --package --out spike_outputs
```

Cleaning is treated as layered modeling, not deletion. You can clip extreme
outliers, smooth the main signal, and optionally store the raw-minus-cleaned
residual as a separate noise layer:

```powershell
py -m vizcompress.cli build --synthetic 100000 --synthetic-kind noisy --sigma-clip 2.5 --smooth-window 51 --noise-layer-terms 32 --channel --package --out noisy_outputs
```

Use `--auto-noise-layer` to add a Fourier residual layer only when residual
analysis recommends it. If the residual looks like sparse outliers instead, the
tool stores a sparse residual layer rather than forcing Fourier.

Build the first channel model, where Fourier produces the center function and
the residual band becomes a visual fidelity envelope:

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --svg-samples 1200 --channel --channel-k 3 --channel-window 501 --out channel_outputs
```

Add `--package` to write a minimal `.vizasset` directory for editor/RRKAL
handoff:

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --channel --package --out channel_outputs
```

Outputs:

```text
smoke_outputs/
  direct.svg                # only when --direct-svg is enabled
  rdp_vectorized.svg
  fourier_vectorized.svg
  fourier_channel.svg       # only when --channel is enabled
  demo.py
  metrics.json
  model.vizretain/          # default --package profile
    asset.json
    model.npz
    preview.svg
    metrics.json
    demo.py
```

CSV input is also supported:

```powershell
py -m vizcompress.cli build --csv data.csv --x-column time --y-column value --out outputs
```

Run a size sweep to compare direct SVG growth against model-backed package
growth:

```powershell
py -m vizcompress.cli bench --synthetic-sizes 1000,10000,100000 --synthetic-kind spikes --fourier-terms 96 --svg-samples 1200 --channel --out benchmark_outputs/spike_sweep.json
```

The benchmark reports direct SVG bytes, gzip-compressed direct SVG bytes,
estimated source CSV bytes, estimated source CSV.gz bytes, `.vizasset` bytes,
model bytes, preview bytes, fidelity metrics, the direct-SVG-to-package size
ratio, and the first observed sample count where the model-backed package wins.
Rows also include `x_domain_mode`, so irregular time-axis overhead is visible.
For irregular time series, package builds can use `--x-domain-policy compressed`
to store the x-axis as a linear domain plus compressed delta instead of full
`x_values`. Benchmark rows report x-domain parameter count, RMSE, and max
absolute x error.
Use `--x-domain-policy auto --x-domain-max-error 0.0001` to compress the domain
only when the selected encoding stays within the error budget.

Use `--synthetic-kind all` to run the same sweep across every built-in synthetic
fixture. The output includes both a global `summary` and `summary_by_kind` for
per-dataset break-even analysis.
Each row also includes a `recommendation` label such as
`package_preferred`, `direct_svg_preferred`, or
`package_smaller_but_low_fidelity`.
Rows also include `gzip_recommendation`, which uses gzip-compressed direct SVG
as the baseline and can surface cases such as
`package_beats_raw_svg_but_not_gzip`.
Summaries include `recommendation_counts` and `gzip_recommendation_counts` so
the whole sweep can be scanned without reading every row.

Summarize an existing benchmark report:

```powershell
py -m vizcompress.cli recommend benchmark_outputs/all_kinds_matrix.json
```

Package suffixes are format-family aliases:

- `.vizretain`: keeps residual/noise layers when available.
- `.vizclean`: exports only the cleaned main signal and its preview/metrics.
- `.vizasset`: neutral container name accepted by the loader.

Inspect a package and verify that it can reconstruct renderable arrays:

```powershell
py -m vizcompress.cli inspect channel_outputs/model.vizretain --samples 1200
```

Validate a package manifest, file hashes, model arrays, x-domain encoding, and
basic reconstruction path:

```powershell
py -m vizcompress.cli verify channel_outputs/model.vizretain --samples 1024
```

When the original source is available, verify decoded fidelity against the
source under an explicit error budget:

```powershell
py -m vizcompress.cli verify channel_outputs/model.vizretain --synthetic 100000 --max-rmse 0.01
```

Build can also write a review packet next to the package. The review packet
records the source fingerprint, verification policy, package self-check, and
source-fidelity metrics. It also records package bytes versus source numeric
array bytes as first-pass compression evidence. When `--direct-svg` is enabled,
the review also records direct SVG raw bytes, gzip bytes, and baseline-to-package
ratios:

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --direct-svg --package --review-packet --review-max-rmse 0.01 --out reviewed_outputs
```

Add `--require-review-pass` when a failing review should fail the build instead
of only writing `accepted: false` to `review.json`.

Compare an existing package against baseline files without rebuilding it:

```powershell
py -m vizcompress.cli compare reviewed_outputs/model.vizretain --baseline direct_svg=reviewed_outputs/direct.svg
```

## Status

Phase 0/1 implementation has started. The package currently supports synthetic and CSV time-series compression through RDP and Fourier, with SVG, `demo.py`, and metrics exports. Phase 2 has a first Fourier channel prototype for center-line plus residual-band visual models.
