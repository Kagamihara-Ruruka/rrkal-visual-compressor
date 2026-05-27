# Functional Video Compression Prototype

## Core hypothesis

For an animation sequence, a raw tensor is:

$$
V = \{I_t\}_{t=1}^{T}, \quad I_t \in \mathbb{R}^{H\times W}
$$

This project treats the whole sequence as a function over time plus space:

$$
V(t, x, y) \approx \sum_{k=1}^{r} c_k(t)\,\phi_k(x,y) + \bar{I}(x,y)
$$

where:

- $\phi_k$ are spatial modes (SVD/POD),
- $c_k(t)$ are temporal trajectories,
- $\bar{I}$ is the temporal mean frame.

We model each $c_k(t)$ with a separable Fourier model.  
That yields a two-layer compressor:

1. encode spatial basis once,
2. encode each temporal mode with a small frequency set,
3. reconstruct frames only where the viewport asks for them.

## Why this is useful for your “rendering-as-function” plan

This gives a concrete implementation of:

$$
O = \mathrm{render}(E, v, b, s)
$$

where:

- $E$ is encoded assets (`spatial_modes`, Fourier coeffs),
- $v$ is viewport/LOD policy,
- $b$ is budget (frame budget / error budget),
- $s$ is style/shader policy.

The result is not “draw every point first.”  
It decodes directly into render-ready numeric buffers for the required frame count.

## What to validate first (strictly testable)

- Temporal reconstruction error:
  - RMSE, MAE, max-abs in pixel space.
- Parametric footprint:
  - size of mean + spatial basis + Fourier params.
- Break-even:
  - `size_ratio = raw_bytes / model_bytes`.
- Throughput:
  - reconstruction time for target output FPS at chosen output frame count.

We should only claim win when evidence beats a baseline:

$$
|C_{video}| + |M_{meta}| < |B_{baseline}|
$$

## Experimental baseline path for this repo

Current prototype includes:

- `VideoCube`: structured frame sequence input.
- `compress_video`: low-rank spatial decomposition + Fourier temporal models.
- `reconstruct_video_at_samples`: rendering at arbitrary output frame count.
- `estimate_video_model_ratio`: feasibility evidence with raw/model size + RMSE/R2.

## Risk notes

- Constant or noisy videos are not uniformly compressible by this route.
- SVD is expensive for huge videos if done naively; practical systems should add:
  - downsample-before-SVD,
  - randomized SVD,
  - blocked updates per time chunk.
- This is a valid phase-0 research path for “function-first video rendering,” not a
  universal claim.
