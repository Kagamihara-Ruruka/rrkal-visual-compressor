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

## Cross-machine reproducibility check

For parity between `K:` and local `C:` copies, generate the same artifact in both
places with the same parameters, then compare hash and key gate fields:

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

# compare
Get-FileHash docs/benchmarks/ci_terms_channel_kind_threshold_sweep.json
```

If hashes differ, it is usually one of:
- Working-copy code drift (`K:` and `C:` commits differ).
- Environment/seed drift from unpinned dependencies.
- Missing function compatibility (`c` workspace running older code snapshot).

`C:` workspace should be aligned to the same commit as `K:` before taking an
evidence claim.
