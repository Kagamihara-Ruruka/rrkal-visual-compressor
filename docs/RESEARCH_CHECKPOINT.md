# Research Checkpoint v1.1: Defensible Compression Roadmap

Date: 2026-05-28  
Owner: RRKAL Visual Compressor  
Scope: time-series / 2D preview layer (not yet 3D engine)

## 1) Core claim (currently tested)

We are not proving a universal theorem.  
Current hypothesis is:

> For data with explicit structure (smooth trend + local detail + moderate noise), a
> compact functional representation plus bounded residual layer can outperform raw
> point sampling under measured constraints.

This stays a **testable engineering claim**, not a physics law.

## 2) Current risk hypotheses (already converted into checks)

1. **Global Fourier locality bleed**  
   sharp jumps can create non-local ripple artifacts.  
   ✅ measured by `locality_leakage_metric`.

2. **Irregular `x` handling**  
   irregular timestamps need explicit domain policy in decode/encode.  
   ✅ existing `domains.py` options + payload path checks are in place.

3. **Channel coupling**  
   channels are not independent in real systems.  
   ✅ PCA/SVD multi-axis test path added.

4. **Residual budget blow-up**  
   second-layer correction can erase compression gains.  
   ✅ residual ratio and payload estimate now tracked.

5. **View-aware sampling budget**  
   over-sampling beyond display resolution is wasteful.  
   ✅ RDP pre-filter path exists + frontier sweep added.

## 3) New gate policy for this checkpoint

For each row in `scripts/run_defensible_research_sweep.py`:

- `R2 >= r2_gate` (default `0.99`)
- locality candidates pass under chosen mode:
  - `strict` (default): piecewise Fourier and detrended Fourier must pass
  - `any`: either one can pass
- optional piecewise polynomial candidate with `--include-piecewise-polynomial`
- `adaptive_keep_ratio <= max_adaptive_keep_ratio` (default `0.45`)

Rows satisfying all become `defensible = true`.

## 4) RDP frontier scan (new)

Command:

```bash
py scripts/run_defensible_research_sweep.py \
  --terms 16,32 \
  --include-piecewise-polynomial \
  --run-rdp-frontier \
  --rdp-frontier-ratios 0.02,0.05,0.10,0.20,0.30 \
  --out-json docs/benchmarks/defensible_hardening_report_frontier.json \
  --out-md docs/benchmarks/defensible_hardening_report_frontier.md
```

This adds:

- per-dataset/per-term sweep rows at each target keep ratio
- actual kept ratio and payload ratio for each sweep point
- best point under `r2_gate` for quick sweet-spot review
- monotonic sanity flag (`actual_keep_ratio` should be non-decreasing as target increases)

## 5) How to advance / rollback

Advance when:

- artifacts are reproducible (JSON + MD with same command)
- at least one non-trivial gate pass exists in fixed dataset set:
  `steps`, `spikes`, `irregular`, `multiscale`, `smooth`
- frontier sweep monotonic flag is stable (`>= 80%` of rows true)
- `tests/test_research_sweep.py` passes, so the frontier parser and best-point
  selection are guarded by unit tests
- noise frontier is reproducible with fixed seed and records when higher sigma
  causes `r2_below_gate`

Regress immediately if:

- hard failures repeat in two consecutive checkpoints
- frontier best points drift while using same seeds and same command

## 6) Next execution step

- tighten gates in small increments
- introduce deterministic `noise_budget` splits (low/medium/high noise) before model expansion
- expand noise frontier from synthetic `smooth` into `spikes` and `multiscale`
- prepare renderer-side benchmark: decode cost vs raster budget coupling
