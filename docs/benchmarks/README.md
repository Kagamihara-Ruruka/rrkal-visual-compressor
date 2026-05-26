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
