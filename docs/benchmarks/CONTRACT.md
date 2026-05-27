# Benchmark Contract (EN)

This contract defines measurable invariants for CI and repeatable research reports.

## Core checks

For fixed `(synthetic_kind, samples, channel_k)` and fixed profile, increasing Fourier terms should not reduce fidelity:

$$
\forall t_1 < t_2,\quad R^2(t_2)+\epsilon \ge R^2(t_1)
$$

where `R²` is the Fourier fidelity score in each benchmark row.

The validator also checks:

- `channel_coverage_ratio ∈ [0,1]` when present.
- ratio fields are positive finite numbers.
- summary counters agree with row-level recomputation.

## Scope

- Input is a benchmark JSON produced by current sweep scripts.
- This is a **sanity contract**, not a universal guarantee for every model family.

## CLI

```bash
py scripts/validate_benchmark_contracts.py docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json
```

Exit codes:

- `0`: PASS
- `2`: FAIL

## Why this matters

The sequence is:
1. choose a compressed family,
2. define quantifiable acceptance criteria,
3. run a deterministic sweep,
4. validate contract outputs.

This prevents interpretation drift between environments.
