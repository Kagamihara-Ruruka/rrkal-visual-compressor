# Research Notes: Defensible Compression Directions (RRKAL Visual Compressor)

Date: 2026-05-27  
Project: `rrkal-visual-compressor`

## 1) Scope and interpretation

This repo is now focused on making the compression path defensible, not on proving a new universal math theorem.
We only keep methods that pass measurable constraints:

- same input series, same evaluation sample count;
- explicit reconstruction metrics (R²/RMSE/Max-AE) under same tolerance targets;
- explicit payload/complexity metrics (coeff count, kept residual ratio, metadata size signal);
- separate reporting for fidelity and compression ratio.

## 2) Current risk model (hard constraints)

### Risk A: Global locality diffusion
Global Fourier tends to smear local events across the full signal (classic Gibbs / global-basis issue).

- We use `locality_leakage_metric` in `src/vizcompress/research.py` as a guard.
- Step-like series are used as stress cases.

Current reading: the piecewise baselines reduce local artifact severity on discontinuities for the tested datasets, but this is not a proof of dominance.

### Risk B: Irregular x-domain
Irregular timestamps can silently break reconstruction assumptions.

- Domain handling in production is controlled by `domains.py` (`stored_x`, `linear_plus_rdp_delta`, `linspace_from_min_max`).
- `packages.py` validation was fixed for linear-plus-compressed x arrays (`x_delta_t`, `x_delta_values`).

### Risk C: Channel coupling
Per-channel independent Fourier ignores structure across channels.

- `compress_multichannel_fourier_pca` adds a PCA/SVD shared-latent stage before Fourier.

### Risk D: Residual payload blow-up
Residual layers may carry most of the entropy and wipe out compression gains.

- We track payload through `metrics` and now include `residual_payload_ratio` in wavelet baseline experiments.

## 3) Implemented research baselines

`src/vizcompress/research.py` now includes:

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold` (Haar basis + hard threshold)
- `locality_leakage_metric`

`tests/test_research.py` now covers:

- discontinuity leakage comparison
- polynomial + piecewise finite checks
- irregular sampling diagnostics
- multichannel PCA baseline
- Haar threshold baseline

## 4) New insight: polyline simplification as rendering-aware sampling

Your "polyline simplification" idea is conceptually consistent and important.
In rendering terms, it is not a different compression philosophy; it is the **sampling budget policy** that should come before geometric evaluation:

- If the target raster is `W×H` and the visible span width is `P` pixels, sampling above Nyquist (roughly `2P` points) is redundant.
- A simplification layer (Ramer-Douglas-Peucker, angle/curvature pruning, or adaptive knot removal) can cut point count before any function fit.
- The function layer (Fourier/polynomial/wavelet) then approximates the already-thinned signal.

This gives a stable workflow:
1. decide target display resolution / viewport uncertainty band,
2. perform simplification under tolerance ε related to screen pixel pitch,
3. compress simplified sequence with a local basis.

So yes, this concept is stable as an engineering principle. It is also testable:
- stability over scale levels,
- monotonic error vs ε,
- reduction in residual payload.

## 5) Execution checklist

```bash
python -m pytest tests/test_research.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32,64 --out-json docs/benchmarks/defensible_hardening_report.json --out-md docs/benchmarks/defensible_hardening_report.md
```

## 6) Interpreting outcomes

- If R² rises but payload ratio rises similarly, not a net win.
- If locality improves but fidelity regresses severely on spikes/steps, not production-ready.
- If both fidelity and payload improve under the same ε/terms budget, we can graduate a baseline to roadmap.

