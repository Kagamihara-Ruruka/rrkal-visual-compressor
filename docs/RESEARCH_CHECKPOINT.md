# Research Checkpoint v1.1: Defensible Compression Roadmap

Date: 2026-05-28  
Owner: RRKAL Visual Compressor  
Scope: time-series / 2D preview layer, not yet 3D engine

## 1) Core claim currently tested

We are not proving a universal theorem.  
Current hypothesis is:

> For data with explicit structure, such as smooth trend, local detail, and moderate noise, a compact functional representation plus bounded residual layer can outperform raw point sampling under measured constraints.

This stays a **testable engineering claim**, not a physics law.

## 2) Current risk hypotheses

1. **Global Fourier locality bleed**  
   Sharp jumps can create non-local ripple artifacts.  
   Measured by `locality_leakage_metric`.

2. **Irregular `x` handling**  
   Irregular timestamps need explicit domain policy in decode/encode.  
   Existing `domains.py` options and payload path checks are in place.

3. **Channel coupling**  
   Channels are not independent in real systems.  
   PCA/SVD multi-axis test path added.

4. **Residual budget blow-up**  
   Second-layer correction can erase compression gains.  
   Residual ratio and payload estimate are now tracked.

5. **View-aware sampling budget**  
   Over-sampling beyond display resolution is wasteful.  
   RDP pre-filter path exists and frontier sweep has been added.

## 3) Gate policy for this checkpoint

For each row in `scripts/run_defensible_research_sweep.py`:

- `R2 >= r2_gate`, default `0.99`
- locality candidates pass under chosen mode:
  - `strict`: piecewise Fourier and detrended Fourier must pass
  - `any`: either method can pass
- optional piecewise polynomial candidate with `--include-piecewise-polynomial`
- `adaptive_keep_ratio <= max_adaptive_keep_ratio`, default `0.45`

Rows satisfying all gates become `defensible = true`.

## 4) RDP frontier scan

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
- best point frontier tier: `strict_pass`, `exploratory_pass`, `demo_pass`, `reject`, `payload_reject`
- monotonic sanity flag: `actual_keep_ratio` should be non-decreasing as target increases
- tier histogram in both JSON summary and Markdown output
- optional tier matrix via `--run-frontier-tier-matrix`, which re-scores the same frontier sweeps across `frontier_exploratory_r2_gates` and `frontier_demo_r2_gates`
- noise frontier tier summaries grouped by `sigma` and `base_kind`
- noise frontier recommendation, which converts tier failures into a next experiment label rather than a success claim
- local strategy probe comparing current RDP, Haar/local basis, and sparse residual signals without promoting any branch to production
- sparse residual frontier that measures top-residual correction budgets against the detrended Fourier base
- sparse residual promotion gate using the same `r2_gate` and payload gate language as other frontiers
- sparse residual escalation diagnostic that retries failed rows with larger residual budgets, reporting the minimum promotable residual budget so we can tell whether a failure is a budget issue or a model-family issue
- residual budget tier labels:
  `cheap_residual` below 5%, `moderate_residual` from 5% through 10%, and `expensive_residual` above 10%
- residual escalation recommendation, which turns the budget tier mix into a next experiment label without claiming the residual layer is production-ready

## 5) Advance / rollback rules

Advance when:

- artifacts are reproducible from the same command
- at least one non-trivial gate pass exists in the fixed dataset set: `steps`, `spikes`, `irregular`, `multiscale`, `smooth`
- frontier sweep monotonic flag is stable, at least 80% of rows pass
- `tests/test_research_sweep.py` passes, guarding ratio parsing, best-point selection, and frontier tiers
- noise frontier is reproducible with fixed seed and records when higher sigma causes `r2_below_gate`
- frontier candidates satisfy both fidelity and storage gates: `r2_gate` and `frontier_min_payload_ratio`

Regress immediately if:

- hard failures repeat in two consecutive checkpoints
- frontier best points drift under the same seed and same command

## 6) Next execution step

- tighten gates in small increments
- introduce deterministic low/medium/high `noise_budget` splits before model expansion
- use the tier matrix to decide which exploratory/demo gate pair is stable enough for reporting
- compare noise frontier behavior across `smooth`, `spikes`, and `multiscale`
- use tier-by-sigma and tier-by-kind summaries to decide whether residual, wavelet, or adaptive segmentation should be promoted next
- treat `recommended_next_strategy` as an experiment queue item, not as proof that the chosen method will pass the strict gate
- use the local strategy probe table to decide whether Haar/local basis or sparse residual should get the next implementation checkpoint
- use sparse residual frontier best points to decide whether residual retention should become the next promoted research branch
- only promote residual retention after the sparse residual frontier reports promotable rows, not merely positive R2 delta
- inspect sparse residual escalation before changing model families; if a failed row passes only after a much larger residual budget, record the payload tradeoff explicitly
- treat `expensive_residual` as a warning to test higher terms, local basis, wavelet, or adaptive segmentation before declaring the residual layer efficient
- treat residual escalation recommendation as a queue pointer; verify it with the next benchmark before changing default compression behavior
- prepare renderer-side benchmark: decode cost vs raster budget coupling
