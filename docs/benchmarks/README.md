# Benchmark Evidence

This folder stores small, reviewable benchmark artifacts that can be rerun from
the CLI. These files are not raw datasets; they are compact evidence snapshots
for validating compression claims.

## Artifacts

- `smooth_100k_terms_sweep.json`: machine-readable benchmark evidence for a
  100,000-sample smooth synthetic series with Fourier terms `32,64,96`.
- `smooth_100k_terms_sweep.md`: human-readable summary of the same run.
- `smooth_100k_channel_k_sweep.json`: machine-readable channel coverage sweep
  for K values `2,2.5,3,3.5,4`.
- `smooth_100k_channel_k_sweep.md`: human-readable summary of the same run.
- `fourier_sweep_16_32_threshold_0995.json`: 10,000-sample Fourier term sweep
  with `16,32` and coverage policy `0.995`.
- `fourier_sweep_16_32_threshold_0995.md`: human-readable summary of the same run.
- `fourier_sweep_10k_16_32_threshold_0995.json`: same sweep command with
  explicit window and epsilon settings for coverage stress testing.
- `fourier_sweep_10k_16_32_threshold_0995.md`: human-readable summary of the same run.
- `defensible_threshold_sweep_10k_16_terms.json`: coverage threshold sensitivity
  sweep for `16` terms.
- `defensible_threshold_sweep_10k_16_terms.md`: human-readable summary of the same run.
- `terms_channel_k_grid.json`: joint sweep artifact for Fourier term and channel-K grid.
- `terms_channel_k_grid.md`: human-readable report for term-K sweep frontiers.
- `terms_channel_k_threshold_grid.json`: term-K frontiers across defensible thresholds.
- `terms_channel_k_threshold_grid.md`: human-readable report for threshold-vs-frontier behavior.
- `terms_channel_kind_threshold_grid.json`: term-K frontiers across kinds and defensible thresholds.
- `terms_channel_kind_threshold_grid.md`: human-readable report for kind-level stability.
- `terms_channel_kind_threshold_grid_10k.json` / `_10k.md`: sample run with gate-ready kind sweep dataset.
- `terms_channel_kind_threshold_grid_10k_gate.json` / `_10k_gate.md`: gate-enabled kind sweep with defensible constraints.
- `terms_channel_kind_threshold_grid_5k_hard.json` / `_5k_hard.md`: hard-signal sweep (`noisy,spikes,steps`) as robustness probe.
- `terms_channel_kind_threshold_grid_5k_noiseclean.json` / `_5k_noiseclean.md`: hard-signal sweep with `--sigma-clip 2.5 --auto-noise-layer`.
- `defensible_hardening_report_terms64.json` / `.md`: research hardening sweep with Fourier terms `16,32,64`; used to check whether higher terms reduce sparse residual budget before adding a new model family.

- `README.zh-TW.md`: benchmark governance and validation notes in Traditional Chinese.

## Current Reading

The smooth 100k terms sweep shows that all tested Fourier term counts beat both
SVG.gz and source CSV.gz under an R2 gate of `0.99`.

The practical sweet spot is not just the smallest package. In this run, `32`
terms has the best size ratio but under-covers the channel band. `96` terms is
slightly larger but reaches `package_preferred_against_gzip`, so it is the
better current default for channel-backed visual assets.

The channel K sweep deliberately records a failed coverage gate at `0.9` for K
values below `3`. This is useful negative evidence: the current smooth 100k
fixture needs roughly K >= `3` before the channel model becomes defensible.

The defensible candidate threshold is configurable through
`--defensible-channel-coverage` in `vizcompress.cli bench`. The same benchmark
artifact can therefore expose either a looser default sweep (`0.9`) or a stricter
operational policy (`>=0.98`) without re-running unrelated model settings.

The `defensible_hardening_report_terms64` artifact is current negative/positive
evidence for spike-like data. In the latest run, `spikes/16` needs `20%`
residual retention, `spikes/32` needs `10%`, and `spikes/64` passes the default
`5%` sparse residual frontier. This supports testing higher terms before
promoting a separate local model family.

### Defensive Evidence Pattern (中文同義: 防禦式證據)

Each benchmark summary now includes two gate counters:

- `High-fidelity rows`: candidate rows with `R2 >= 0.99`.
- `Defensible rows`: among high-fidelity rows, those whose channel coverage also reaches
  `--defensible-channel-coverage`.

This lets you report both:

- 壓縮率的最佳候選 (best ratio),
- 以及在重建保真門檻下可被採信的比例 (defensible ratio).

```bash
py -m vizcompress.cli bench \
  --synthetic-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms-sweep 16,32 \
  --channel \
  --channel-k 3 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --defensible-channel-coverage 0.995 \
  --svg-samples 240 \
  --rdp-epsilon 0.6 \
  --out docs/benchmarks/fourier_sweep_10k_16_32_threshold_0995.json \
  --report-md docs/benchmarks/fourier_sweep_10k_16_32_threshold_0995.md
```

For Fourier sweeps, see:

```bash
py -m vizcompress.cli bench \
  --synthetic-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms-sweep 16,32 \
  --channel \
  --channel-k 3 \
  --defensible-channel-coverage 0.995 \
  --svg-samples 240 \
  --out docs/benchmarks/fourier_sweep_16_32_threshold_0995.json \
  --report-md docs/benchmarks/fourier_sweep_16_32_threshold_0995.md
```

This command writes both `docs/benchmarks/fourier_sweep_16_32_threshold_0995.json`
and `...md`, where `summary_by_terms` is expected to preserve the same threshold.

For threshold sensitivity, see:

```bash
py scripts/run_defensible_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms 16 \
  --thresholds 0.8,0.9,0.95,0.98,0.995 \
  --channel \
  --channel-k 3 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --out-json docs/benchmarks/defensible_threshold_sweep_10k_16_terms.json \
  --out-md docs/benchmarks/defensible_threshold_sweep_10k_16_terms.md
```

For two-dimensional frontiers (terms × channel K):

```bash
py scripts/run_terms_channel_grid_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --svg-samples 240 \
  --out-json docs/benchmarks/terms_channel_k_grid.json \
  --out-md docs/benchmarks/terms_channel_k_grid.md
```

For stability of defensibility (terms × channel K × threshold):

```bash
py scripts/run_terms_channel_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90,0.92,0.95,0.98,0.995 \
  --svg-samples 240 \
  --out-json docs/benchmarks/terms_channel_k_threshold_grid.json \
  --out-md docs/benchmarks/terms_channel_k_threshold_grid.md
```

For stability across all synthetic kinds:

```bash
py scripts/run_terms_channel_kind_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kinds all \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90,0.92,0.95,0.98 \
  --svg-samples 240 \
  --out-json docs/benchmarks/terms_channel_kind_threshold_grid.json \
  --out-md docs/benchmarks/terms_channel_kind_threshold_grid.md
```

Add quality gates for automatic feasibility checks:

```bash
py scripts/run_terms_channel_kind_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kinds all \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90,0.92,0.95,0.98 \
  --svg-samples 240 \
  --require-svg-gzip-win \
  --min-defensible-ratio 0.2 \
  --out-json docs/benchmarks/terms_channel_kind_threshold_grid.json \
  --out-md docs/benchmarks/terms_channel_kind_threshold_grid.md
```

### Contract validation

Use the benchmark contract validator to enforce measurable assumptions before
claiming cross-model comparability:

```bash
py scripts/validate_benchmark_contracts.py \
  docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json \
  --out docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate_contract.json
```

Contract checks include:

- `fourier_r2` non-decrease as Fourier terms increase for fixed
  `(synthetic_kind, samples, channel_k)`.
- Coverage ratio is bounded in `[0,1]` when provided.
- Compression ratios are finite and positive.
- Summary counters are consistent with row-level recomputation.

To validate all benchmark JSON files in a folder:

```bash
py scripts/validate_benchmark_contracts_all.py \
  --root docs/benchmarks \
  --out docs/benchmarks/contract_matrix_latest.json
```

Legacy hardening reports can be converted to contract-shaped artifacts with this command:

```bash
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run
```

Use without `--dry-run` only on a controlled one-off migration after review, which writes:

- `<original>_contract.json` for each recognized `defensible_hardening_report*.json`.
- rows converted into current contract fields.
- `_legacy_source` and `_legacy_defensible` tags for provenance and audit.

This prints PASS/FAIL per file and returns a non-zero exit code on any failure.

Run both field scan and contract checks in one precheck command before opening
pull requests or promoting artifacts. For local manual promotion, treat this command
as mandatory:

```bash
py scripts/precheck_benchmarks.py \
  --root docs/benchmarks \
  --pattern "*.json" \
  --scan-out docs/benchmarks/scan_report.json \
  --contract-out docs/benchmarks/contract_matrix_precheck.json \
  --fail-on-scan-warning
```

The precheck prints a JSON summary with:

- `scan_ok`: fast field scan result.
- `contract_ok`: strict contract result.
- `scan.summary`: aggregated scan metrics.
- `contract`: `failed/passed/total` counters and `status`.
- `failed_report`: contract report path when strict checks fail.
- `status_counts` and `skipped` (plus `skip_reasons`): non-contract payloads are reported with explicit skip reasons.
- `total_inputs`: total files considered by the precheck run.

In CI, keep `--fail-on-scan-warning` enabled so malformed benchmark JSON is
blocked early, and keep both reports (`scan` + contract) for auditability.

For K/C reproducibility plus contract safety checks in one command:

```bash
py scripts/compare_terms_channel_benchmark_parity.py \
  --left-root "L:\\rrkal-visual-compressor" \
  --right-root "L:\\rrkal-visual-compressor" \
  --sample-sizes 1000 \
  --synthetic-kinds smooth \
  --fourier-terms 16 \
  --channel-k 3 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90 \
  --svg-samples 120 \
  --left-out-json docs/benchmarks/ci_left.json \
  --right-out-json docs/benchmarks/ci_right.json \
  --report-json docs/benchmarks/ci_compare_report.json \
  --validate-contract
```

The generated report JSON includes machine-checkable status:

- `status: ok` all checks pass
- `status: contract_failed` contract gate failed
- `status: signature_mismatch` semantic signature mismatch while hash differs
- `status: parity_failed` hash mismatches after tolerances
- `contract_validation.enabled` indicates contract checking mode
- `contract_validation.enforced` is true only with `--require-contract-pass`
- `contract_validation.left/right` summarize per-side contract outcomes
- `contract_validation.left_passed/right_passed` are boolean pass flags
- `contract_violations` lists contract-fail summaries

By default, parity contract checks are opt-in in this script.
In CI, use a strict contract gate with:

```bash
py scripts/compare_terms_channel_benchmark_parity.py ... --validate-contract --require-contract-pass
```

### Hard-signal behavior note

In `5k_hard`, `noisy` and `spikes` rows show little or no high-fidelity coverage (`R²>=0.99`) at this scale, while `steps` remains stable and yields the best ratio.

In `5k_noiseclean` (`sigma_clip + auto_noise_layer`) this tendency persists, indicating that the current residual defaults still underperform for this dataset family under the strictness of the existing `R²` gate and require either:

- stronger denoising before modeling,
- a relaxed fidelity gate for this domain,
- or domain-specific profile tuning (channel settings, terms budget, or additional model components).

## Cross-machine reproducibility check

For parity between `K:` and local `C:` copies, generate the same artifact in both
places with the same parameters, then compare hash and key gate fields:

Use the benchmark parity utility (`_k` from K copy, `_c` from C copy):

```bash
py scripts/run_terms_channel_kind_threshold_sweep.py \
  --sample-sizes 1000 \
  --synthetic-kinds smooth \
  --fourier-terms 16 \
  --channel-k 2 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90 \
  --svg-samples 120 \
  --out-json docs/benchmarks/ci_terms_channel_kind_threshold_sweep.json \
  --out-md docs/benchmarks/ci_terms_channel_kind_threshold_sweep.md
```

Copy the exact JSON to the counterpart workspace, then run `check_benchmark_parity.py` in either side:

```bash
py scripts/check_benchmark_parity.py \
  --left docs/benchmarks/ci_terms_channel_kind_threshold_sweep_k.json \
  --right docs/benchmarks/ci_terms_channel_kind_threshold_sweep_c.json
```

You can also run the parity regression tests directly in CI/test environments:

```bash
py -m pytest tests/test_benchmark_parity.py
```

A pass here guarantees the script accepts:

- identical files (`hash: MATCH`)
- metadata-only differences (`logical_signature: PASS`)
- key-value diffs (`logical_signature: FAIL`)

If hashes differ, it is usually one of:
- Working-copy code drift (`K:` and `C:` commits differ).
- Environment/seed drift from unpinned dependencies.
- Missing function compatibility (`c` workspace running older code snapshot).

`C:` workspace should be aligned to the same commit as `K:` before taking an
evidence claim.
