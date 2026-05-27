# Research Notes: Defensible Compression Directions (RRKAL Visual Compressor)

Date: 2026-05-27  
Project: `rrkal-visual-compressor`

## 1) Scope and interpretation

This repo is now focused on making the compression path defensible, not on proving a new universal math theorem.
We only keep methods that pass measurable constraints:

- same input series, same evaluation sample count;
- explicit reconstruction metrics (R2/RMSE/Max-AE) under the same tolerance targets;
- explicit payload/complexity metrics (coefficient count, kept residual ratio, metadata size);
- separate reporting for fidelity and compression ratio.

## 2) Current risk model (hard constraints)

### Risk A: Global locality diffusion
Global Fourier tends to smear sharp local changes across the whole signal (classic Gibbs / global-basis issue).

- We use `locality_leakage_metric` in `src/vizcompress/research.py` as a guard.
- Step-like synthetic cases are included to stress this behavior.

Current reading: piecewise baselines reduce local artifact severity on discontinuities in tested datasets, but this is not dominance proof.

### Risk B: Irregular x-domain
Irregular timestamps can silently break reconstruction assumptions.

- Domain handling in production is controlled by `domains.py` (`stored_x`, `linear_plus_rdp_delta`, `linspace_from_min_max`).
- `packages.py` validation was fixed for linear-plus-compressed x arrays (`x_delta_t`, `x_delta_values`).

### Risk C: Channel coupling
Per-channel independent Fourier ignores cross-channel structure.

- `compress_multichannel_fourier_pca` adds a PCA/SVD shared-latent stage before Fourier.

### Risk D: Residual payload blow-up
Residual layers may carry most of the entropy and remove compression gains.

- We track payload through `metrics` and include `residual_payload_ratio` in wavelet baseline experiments.

## 3) Implemented research baselines

`src/vizcompress/research.py` now includes:

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold` (Haar basis + hard threshold)
- `locality_leakage_metric`
- `compress_fourier_with_linear_detrend` (linear de-trend + Fourier)
- `adaptive_residual_threshold` (volatility-driven residual masking)
- `compress_fourier_with_rdp_budget` (viewport-aware RDP + Fourier)

`tests/test_research.py` now covers:

- discontinuity leakage comparison
- polynomial + piecewise finite checks
- irregular sampling diagnostics
- multichannel PCA baseline
- Haar threshold baseline
- linear de-trend + Fourier baseline
- adaptive residual threshold baseline

## 4) Polyline simplification as rendering-aware sampling

Your polyline simplification idea is conceptually consistent and important.
In rendering terms, it is not a different compression philosophy; it is the **sampling budget policy** that should come before geometric evaluation:

- If the target raster is `W×H` and visible span in pixels is `P`, sampling above Nyquist (roughly `2P` points) is redundant.
- A simplification layer (RDP, angle/curvature pruning, or adaptive knot removal) can reduce point count before any function fitting.
- The function layer (Fourier/polynomial/wavelet) then approximates the already-thinned signal.

This is testable:
- stability across scale levels,
- monotonic error vs epsilon,
- reduction in residual payload.

### 4.1) RDP budget baseline now measured

We added a dedicated baseline `compress_fourier_with_rdp_budget`:

- choose `target_keep_ratio` from viewport budget,
- binary-search RDP `epsilon` to reach that keep count,
- fit Fourier on simplified points,
- interpolate back to original domain.

In the current exploratory run (`--locality-mode any`, `--terms 16,32,64`), this baseline:

- improves compute budget at rendering side by reducing input points,
- but can increase total payload if kept points are still too many (because payload includes both RDP control points and Fourier coefficients),
- is therefore currently used as a **separate knob**, not always a default replacement.

Formula (payload proxy in report):

$$
\text{payload}_{rdp} \approx K(2f+8)\;+\;(24C+8)
$$

where:

- $K$ = kept points from RDP,
- $f$ = 8 bytes (float64),
- $C$ = Fourier coefficient count on simplified curve.

---

## 5) Why this is scientifically stable (and where it is not)

The current claim is intentionally narrow:

- we are not claiming universal compression;
- we claim measurable advantage only for a constrained data family with explicit budgets.

This is enforced by three conditions:

1. Scope condition
   - Signal class is predeclared (e.g., smooth, periodic, piecewise-regular, bounded-noise).
   - x-domain contract is recorded and replayed at decode time.
2. Quality condition
   - Same error metric and tolerance are evaluated against the same sample domain.
   - Reproducible seeds and fixtures are used when synthetic data is involved.
3. Complexity condition
   - Compression is measured in total bytes, including coefficients, residuals, metadata, and optional extra compression envelope.

Research outputs are only advanced when all three are satisfied, otherwise methods are marked exploratory.

### Current checkpoint status

- strict mode (`--locality-mode strict`, default): `--terms 16,32,64 --r2-gate 0.99 --leakage-gate 0.25 --max-adaptive-keep-ratio 0.45` produced `0 / 16` defensible rows.
- exploratory mode (`--locality-mode any --r2-gate 0.98 --leakage-gate 0.85 --max-adaptive-keep-ratio 0.45`) produced `12 / 16` defensible rows.

Interpretation:
- strict mode stays a useful "hard claim" baseline (none passed yet).
- any-locality mode is useful to locate where locality is improved by at least one local method before deciding a stronger requirement.
- future checkpoints should fix a single control variable at a time (model family, gates, terms).

### Gate model now in script

- `--locality-mode strict`: both detrended Fourier and piecewise Fourier must be under `--leakage-gate`.
- `--locality-mode any`: at least one of detrended Fourier / piecewise Fourier must be under `--leakage-gate`.
- `--include-piecewise-polynomial`: optionally add polynomial locality to the check set.

## 6) Execution checklist

```bash
python -m pytest tests/test_research.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32,64 --out-json docs/benchmarks/defensible_hardening_report.json --out-md docs/benchmarks/defensible_hardening_report.md
```

## 7) Payload estimation protocol

We are adding a **shared payload proxy** to keep the research defensible:

- `raw_payload_bytes = sample_count * 2 * 8` (float64 x/y baseline),
- Fourier payload `≈ coeff_count * 24 + 8` bytes (`selected_frequencies` + `coefficients` + mean),
- piecewise Fourier payload `≈ Σ segment_fourier_payload + breakpoints*8`,
- piecewise polynomial payload `≈ (approx_parameter_count + 2*segment_count + breakpoints)*8`.

This estimate is intentionally conservative:

- no entropy coding,
- no fixed-point/quantization,
- no container overhead.

The report exposes both raw ratio and each model's `payload_ratio` so we can separate **fidelity gain** from **storage overhead**.

## 8) Interpreting outcomes

- If R2 rises but payload rises similarly, this is not a net win.
- If locality improves but fidelity regresses severely on spikes/steps, do not ship.
- If both fidelity and payload improve under the same epsilon/term budget, we can promote a baseline to roadmap.
