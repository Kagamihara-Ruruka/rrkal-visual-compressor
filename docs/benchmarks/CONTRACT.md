# Benchmark Contract (EN)

This contract defines measurable invariants for CI and repeatable research reports.

This document is authoritative for:

- CI validation output format.
- Dataset quality invariants enforced by `scripts/validate_benchmark_contracts.py` and
  `scripts/validate_benchmark_contracts_all.py`.

## Core checks

For fixed `(synthetic_kind, samples, channel_k)` and fixed profile, increasing Fourier terms should not reduce fidelity:

$$
\forall t_1 < t_2,\quad R^2(t_2)+\epsilon \ge R^2(t_1)
$$

where `R^2` is the Fourier fidelity score in each benchmark row.

The validator also checks:

- `channel_coverage_ratio` is in `[0,1]` when present.
- ratio fields are positive finite numbers.
- summary counters agree with row-level recomputation.
- each error is emitted with a field-level location prefix:
  - `row[<index>].<field>: <message>`
  - `sweep[<index>].<field>: <message>`

Examples:

- `row[3].direct_svg_to_package_ratio: must be >0, got -1.0`
- `row[3].direct_svg_gzip_to_package_ratio: must be >0, got -1.0`
- `sweep[1].high_fidelity_rows_count: missing`
- `docs/benchmarks/.../bad.json: row[0].samples: must be a positive integer, got -1`

## Scope

- Input is a benchmark JSON produced by current sweep scripts.
- This is a sanity contract, not a universal guarantee for every model family.

## CLI

```bash
py scripts/validate_benchmark_contracts.py docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json
py scripts/validate_benchmark_contracts_all.py --root docs/benchmarks
py scripts/scan_benchmark_fields.py docs/benchmarks
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run
py scripts/precheck_benchmarks.py \
  --root docs/benchmarks \
  --pattern "*.json" \
  --scan-out docs/benchmarks/scan_report.json \
  --contract-out docs/benchmarks/contract_matrix_precheck.json \
  --fail-on-scan-warning
```

Exit codes:

- `0`: PASS
- `2`: FAIL

`validate_benchmark_contracts_all.py` also supports `--out`:

- When any file fails, output includes `failed_report: <path>`.
- The summary JSON uses prefixed errors inside `rows[].errors` as `<file>: <error>`.

Quick structural scan:

`scan_benchmark_fields.py` can be used before strict validation to gather:

- mixed row/sweep mode breakdown,
- required-row/sweep missing-field counts,
- unexpected/non-standard field usage.

`precheck_benchmarks.py` returns a compact JSON summary:

- `scan_ok`
- `contract_ok`
- `scan` (scan summary)
- `contract` (pass/fail/total/status)
- `failed_report` (set when contract fails and `--contract-out` is enabled)
- `status_counts` and `skipped` with `skip_reasons` for non-contract/legacy snapshots
- `total_inputs`: total files scanned by the directory pass.

## Why this matters

The sequence is:
1. choose a compressed family,
2. define quantifiable acceptance criteria,
3. run a deterministic sweep,
4. validate contract outputs.

This prevents interpretation drift between environments.

## Compatibility notes

- `channel_k` is optional in row mode and is treated as unspecified when missing.
- `defensible_channel_coverage_threshold` is optional in `summary`; missing means default `0.9`.
- ratio checks treat `bool`, `NaN`, `inf`, and non-finite numbers as invalid.
