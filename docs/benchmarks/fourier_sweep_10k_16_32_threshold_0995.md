# VizCompress Benchmark Report

## Parameters

- Synthetic kind: `smooth`
- Sample sizes: `[10000]`
- Fourier terms: `[16, 32]`
- Channel K values: `3.0`
- SVG samples: `240`
- Channel model: `True`
- X-domain policy: `preserve`

## Summary

- Raw SVG break-even samples: `10000`
- Best raw SVG/package ratio: `6.43913`
- Best SVG.gz/package ratio: `2.27625`
- Best CSV.gz/package ratio: `5.72045`
- High-fidelity rows (R2>=0.99): `2`
- Defensible rows (coverage>= 0.995): `0 (0%)`
- Best defensible high-fidelity SVG.gz candidate (R2>=0.99, coverage>= 0.995): ``
- Best high-fidelity SVG.gz candidate: `smooth / 10000 samples / 16 terms / direct_svg_gzip_to_package_ratio=2.27625 / R2=0.999838 / coverage=0.0786 / package_beats_gzip_but_channel_under_covers`
- Package wins against SVG.gz: `2`
- Package wins against CSV.gz: `2`

## Rows

| kind | samples | terms | channel K | package bytes | SVG.gz/package | CSV.gz/package | LTTB SVG.gz/package | Fourier R2 | LTTB R2 | coverage | gzip recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smooth | 10000 | 16 | 3 | 24865 | 2.27625 | 5.72045 | 0.0759702 | 0.999838 | 0.998708 | 0.0786 | package_beats_gzip_but_channel_under_covers |
| smooth | 10000 | 32 | 3 | 25210 | 2.2451 | 5.64217 | 0.0749306 | 0.999923 | 0.998708 | 0.1076 | package_beats_gzip_but_channel_under_covers |

## Interpretation Guardrails

- A ratio above `1.0` means the model package is smaller than that baseline.
- LTTB is a downsampling baseline, not a package format; its SVG ratio estimates the size after exporting sampled points as a path.
- Higher R2 alone is not enough. The package must also pass source verification and size evidence checks.
