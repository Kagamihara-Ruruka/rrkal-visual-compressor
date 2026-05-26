# VizCompress Benchmark Report

## Parameters

- Synthetic kind: `smooth`
- Sample sizes: `[100000]`
- Fourier terms: `96`
- Channel K values: `[2.0, 2.5, 3.0, 3.5, 4.0]`
- SVG samples: `1200`
- Channel model: `True`
- X-domain policy: `preserve`

## Summary

- Raw SVG break-even samples: `100000`
- Best raw SVG/package ratio: `21.4366`
- Best SVG.gz/package ratio: `6.47073`
- Best CSV.gz/package ratio: `18.3703`
- Best high-fidelity SVG.gz candidate: `smooth / 100000 samples / 96 terms / direct_svg_gzip_to_package_ratio=6.47073 / R2=0.999978 / package_preferred_against_gzip`
- Package wins against SVG.gz: `5`
- Package wins against CSV.gz: `5`

## Rows

| kind | samples | terms | channel K | package bytes | SVG.gz/package | CSV.gz/package | LTTB SVG.gz/package | Fourier R2 | LTTB R2 | coverage | gzip recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smooth | 100000 | 96 | 2 | 74636 | 6.46813 | 18.3629 | 0.105244 | 0.999978 | 0.999995 | 0.61926 | package_beats_gzip_but_channel_under_covers |
| smooth | 100000 | 96 | 2.5 | 74644 | 6.46743 | 18.361 | 0.105233 | 0.999978 | 0.999995 | 0.82567 | package_beats_gzip_but_channel_under_covers |
| smooth | 100000 | 96 | 3 | 74637 | 6.46804 | 18.3627 | 0.105243 | 0.999978 | 0.999995 | 0.95549 | package_preferred_against_gzip |
| smooth | 100000 | 96 | 3.5 | 74612 | 6.47021 | 18.3688 | 0.105278 | 0.999978 | 0.999995 | 1 | package_preferred_against_gzip |
| smooth | 100000 | 96 | 4 | 74606 | 6.47073 | 18.3703 | 0.105286 | 0.999978 | 0.999995 | 1 | package_preferred_against_gzip |

## Benchmark Gate

- OK: `False`
- Policy: `{'require_svg_gzip_win': False, 'require_csv_gzip_win': False, 'min_fourier_r2': 0.99, 'min_channel_coverage': 0.9}`
- Errors: `['2 row(s) below min channel coverage 0.9']`

## Interpretation Guardrails

- A ratio above `1.0` means the model package is smaller than that baseline.
- LTTB is a downsampling baseline, not a package format; its SVG ratio estimates the size after exporting sampled points as a path.
- Higher R2 alone is not enough. The package must also pass source verification and size evidence checks.
