# Functional Compression for Video-like Data

## 1. Core Hypothesis

For a frame sequence,

$$
V = \{I_t\}_{t=1}^{T},\quad I_t\in\mathbb{R}^{H\times W}
$$

We treat the sequence as a **low-rank spatial basis** plus **Fourier temporal coefficients**:

$$
I_t(x,y)\approx \bar I(x,y)+\sum_{k=1}^{r} c_k(t)\,\phi_k(x,y),
$$

where

$$
c_k(t)\approx \sum_{m=1}^{M} a_{k,m}\exp\left(j\omega_m t\right).
$$

The model stores:

- `mean_frame` : spatial mean $\bar I$
- `spatial_modes` : compact basis matrix $\phi_k$
- `temporal_models` : per-mode Fourier coefficients for $c_k(t)$

The decoded representation is a functional model; rendering becomes an evaluation step at the requested output rate.

## 2. Why this matches your "render function" direction

For any downstream renderer, we can define:

$$
O = \mathrm{render}(E,\;N,\;P,\;B),
$$

- $E$: encoded model (not all raw pixels),
- $N$: requested output sample count / target FPS,
- $P$: viewport/LOD policy,
- $B$: output budget (error budget / memory budget).

This lets a UI request only the needed frames at the requested fidelity.

## 3. Current prototype

Current prototype module: `src/vizcompress/video.py`.

It supports:

- `VideoCube` : synthetic / structured frame input,
- `compress_video` : SVD-like spatial decomposition + per-mode Fourier temporal fitting,
- `reconstruct_video_at_samples` : frame-rate agnostic reconstruction,
- `estimate_video_model_ratio` : size and fidelity evidence in one report,
- `src/vizcompress/video_benchmarks.py` : parameter sweeps over frame count / rank / Fourier terms,
- `vizcompress video-bench` CLI entrypoint for reproducible benchmark jobs.

## 4. Evidence that is already defensible

The benchmark output includes:

- compression ratio,
- RMSE / MAE / max error,
- $R^2$,
- model bytes vs raw bytes,
- and row summaries (`best_row`, high-ratio row, high-fidelity row).

These are not only demonstrative numbers; they are machine-checkable.

## 5. What this is *not* claiming

- Not universal compression replacement for all data.
- Not a production `.vizasset` schema for 3D yet.
- Not a direct substitute for raster/mesh renderers in all pipelines.

It is a research-grade path for "compressed functional assets" in a constrained domain.

## 6. Next checkpoint plan

1. Lock deterministic synthetic dataset contract used by `video-bench`.
2. Add a CLI contract test: JSON output schema + recommendation summary.
3. Add a simple 2D-path benchmark row (shape-aware benchmark) once contour tooling is added in later phases.
4. Compare with classical baselines:
   - raw NumPy stack,
   - frame-rate-resolved direct serialization,
   - first-order JPEG/PNG sequences (external reference in future work).

## 7. Related commands

Run a minimal video benchmark:

```powershell
py -m vizcompress.cli video-bench --frame-counts 120,240 --height 32 --width 32 --rank-values 2,4 --temporal-terms-values 8,16 --out benchmark_outputs/video.json --report-md benchmark_outputs/video.md
```

