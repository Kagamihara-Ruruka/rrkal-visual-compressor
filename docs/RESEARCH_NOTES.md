# Research Notes: Defensible Compression Directions (RRKAL Visual Compressor)

Date: 2026-05-28  
Project: `rrkal-visual-compressor`

## 1) Scope and interpretation

This repository focuses on **defensibility**, not a universal compression theorem.
Every claim is conditional and must be testable by reproducible data and metrics.

We evaluate methods only when all of the following are explicit:

- same input sample domain and same evaluation length,
- explicit fidelity metrics (`R2`, `RMSE`, `Max-AE`) under fixed targets,
- explicit complexity and payload metrics (coefficients, residual count, metadata bytes),
- separate reporting of fidelity gain and payload gain.

## 2) Core risks and checks

### A. Global locality diffusion
Global Fourier can spread local anomalies into distant regions.

- `locality_leakage_metric` is used for this check.
- step-like synthetic data is used as a stress test.

### B. Irregular time-domain assumptions
Irregular timestamps can silently shift reconstructions.

- domain policy is explicit in `domains.py` (`stored_x`, `linear_plus_rdp_delta`, `linspace_from_min_max`),
- `packages.py` validates x-domain metadata fields (`x_delta_t`, `x_delta_values`).

### C. Channel coupling
Single-channel Fourier misses shared latent structure in multivariate data.

- `compress_multichannel_fourier_pca` adds a PCA/SVD shared axis stage.

### D. Residual layer overhead
Residuals can erase compression gains if they are too large.

- residual payload ratio and byte estimates are tracked in all comparative rows.

## 3) Implemented baselines

`src/vizcompress/research.py` now includes:

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold`
- `locality_leakage_metric`
- `compress_fourier_with_linear_detrend`
- `adaptive_residual_threshold`
- `compress_fourier_with_rdp_budget`
- `compress_fourier_with_rdp_budget` frontier helper in the sweep script

`tests/test_research.py` now covers:

- discontinuity leakage comparisons,
- local finite-value sanity,
- irregular-domain stability,
- multichannel PCA,
- Haar and adaptive-threshold residual behavior,
- RDP budget constraints and frontier monotonic sanity.

`tests/test_research_sweep.py` now covers:

- CLI ratio parsing for frontier runs,
- invalid ratio rejection,
- RDP frontier monotonic keep behavior,
- best-point selection under an `r2_gate`.

## 4) Rendering-aware simplification = sampling budget control

Your simplification idea is valid:
it is not a different compression language, it is a **budget controller** before fitting.

- `target raster size (W×H)` gives a practical upper bound on visible sample demand.
- extra geometry beyond this bound is often redundant.
- simplification (RDP / curvature pruning / adaptive knots) is applied before Fourier/polynomial/wavelet fitting.
- this usually reduces render-side compute while keeping the same model family.

### 4.1) RDP budget baseline

- Input ratio: `target_keep_ratio`
- Internal search: binary search for `epsilon` in `compress_fourier_with_rdp_budget`
- Fit Fourier on simplified points
- Interpolate back to original x-domain

In the current experiments this can reduce render work but may raise total payload if the kept set stays too large.
Therefore it is currently treated as an orthogonal control variable.

## 5) Frontier scan (new checkpoint instrument)

`scripts/run_defensible_research_sweep.py` now supports:

- `--run-rdp-frontier`
- `--rdp-frontier-ratios`
- `--rdp-frontier-min-keep`
- `--rdp-frontier-max-keep`

The frontier output (JSON + Markdown) records:

- each candidate keep ratio,
- actual retained points and R2,
- payload ratio and kept point count,
- best candidate under `r2_gate`.

This gives a direct way to find "sweet spots" instead of guessing one fixed ratio.

## 6) Payload protocol

Current payload proxies (conservative, no entropy coding):

- `raw_payload_bytes = sample_count * 2 * 8`
- `payload_fourier ≈ parameter_count * 24 + 8`
- `payload_piecewise_fourier = Σ(24 * segment_param_count) + len(breakpoints) * 8`
- `payload_piecewise_polynomial = approx_param_count * 8 + 2 * segment_count * 8 + len(breakpoints) * 8`
- `payload_rdp ≈ kept_points * (2*8 + 8) + payload_fourier`

All outputs also include model-level `payload_ratio = raw_payload_bytes / payload_bytes`.

## 7) How to run

```bash
py -m pytest tests/test_research.py tests/test_research_sweep.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32 --include-piecewise-polynomial --run-rdp-frontier --rdp-frontier-ratios 0.02,0.05,0.10,0.20,0.30
```

## 8) Interpretation rule

- `R2` up, payload up similarly -> not automatically good; check payload ratio trend.
- locality improves but large fidelity regression -> reject.
- stable improvement in both fidelity and payload under fixed terms/budgets -> move toward roadmap.
