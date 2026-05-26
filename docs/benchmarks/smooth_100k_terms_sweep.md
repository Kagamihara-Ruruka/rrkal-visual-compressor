# VizCompress Benchmark Report

## Parameters

- Synthetic kind: `smooth`
- Sample sizes: `[100000]`
- Fourier terms: `[32, 64, 96]`
- SVG samples: `1200`
- Channel model: `True`
- X-domain policy: `preserve`

## Summary

- Raw SVG break-even samples: `100000`
- Best raw SVG/package ratio: `21.4896`
- Best SVG.gz/package ratio: `6.48672`
- Best CSV.gz/package ratio: `18.4157`
- Best high-fidelity SVG.gz candidate: `smooth / 100000 samples / 32 terms / direct_svg_gzip_to_package_ratio=6.48672 / R2=0.999934 / package_beats_gzip_but_channel_under_covers`
- Package wins against SVG.gz: `3`
- Package wins against CSV.gz: `3`

## Rows

| kind | samples | terms | package bytes | SVG.gz/package | CSV.gz/package | LTTB SVG.gz/package | Fourier R2 | LTTB R2 | gzip recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smooth | 100000 | 32 | 74422 | 6.48672 | 18.4157 | 0.105547 | 0.999934 | 0.999995 | package_beats_gzip_but_channel_under_covers |
| smooth | 100000 | 64 | 75952 | 6.35605 | 18.0448 | 0.103421 | 0.999967 | 0.999995 | package_beats_gzip_but_channel_under_covers |
| smooth | 100000 | 96 | 74637 | 6.46804 | 18.3627 | 0.105243 | 0.999978 | 0.999995 | package_preferred_against_gzip |

## Interpretation Guardrails

- A ratio above `1.0` means the model package is smaller than that baseline.
- LTTB is a downsampling baseline, not a package format; its SVG ratio estimates the size after exporting sampled points as a path.
- Higher R2 alone is not enough. The package must also pass source verification and size evidence checks.
