# MVP Checkpoint

This repository now has a one-command MVP path for the time-series visual compression workflow.

## Command

```powershell
py -m vizcompress.cli mvp --samples 20000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 1200 --out mvp_outputs --min-fourier-r2 0.95
```

## What It Proves

The command runs the minimum product loop:

- generate a synthetic large-data time series
- build direct SVG, RDP SVG, Fourier SVG, channel SVG, `demo.py`, `metrics.json`
- write a `.vizretain` package
- validate package manifest, hashes, model arrays, and reconstruction
- validate reconstructed source fidelity
- run a small benchmark against direct SVG.gz and estimated CSV.gz
- write `mvp_summary.json`, `benchmark.json`, and `benchmark.md`

## Latest Smoke Result

Run date: 2026-05-28

- dataset: `spikes`
- samples: `20000`
- Fourier terms: `64`
- status: `pass`
- Fourier R2: `0.987209884017974`
- package bytes: `74688`
- direct SVG.gz bytes: `105679`
- estimated source CSV.gz bytes: `333446`
- direct SVG.gz to package ratio: `1.4149394815766925`
- source CSV.gz to package ratio: `4.464519065981149`
- recommendation: `package_preferred`
- gzip recommendation: `package_preferred_against_gzip`

## MVP Boundary

This is a visual-compression MVP, not a universal compressor.

Accepted claims:

- the project can compile a time series into a compact visual asset
- the asset can be validated and reconstructed
- benchmark evidence can show when the package beats SVG.gz or CSV.gz

Rejected claims:

- every dataset will compress well
- the current Fourier path solves all local discontinuity cases
- this is already a general image/video/3D asset standard

## Next Gate

Before calling the MVP stable, keep these gates green:

```powershell
py -m pytest
py -m vizcompress.cli mvp --samples 20000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 1200 --out mvp_outputs --min-fourier-r2 0.95
```
