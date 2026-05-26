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
- Best raw SVG/package ratio: `5.91113`
- Best SVG.gz/package ratio: `2.0896`
- Best CSV.gz/package ratio: `5.25138`
- Best defensible high-fidelity SVG.gz candidate (R2≥0.99, coverage≥0.995): `smooth / 10000 samples / 16 terms / direct_svg_gzip_to_package_ratio=2.0896 / R2=0.999838 / coverage=0.996 / package_preferred_against_gzip`
- Best high-fidelity SVG.gz candidate: `smooth / 10000 samples / 16 terms / direct_svg_gzip_to_package_ratio=2.0896 / R2=0.999838 / coverage=0.996 / package_preferred_against_gzip`
- Package wins against SVG.gz: `2`
- Package wins against CSV.gz: `2`

## Rows

| kind | samples | terms | channel K | package bytes | SVG.gz/package | CSV.gz/package | LTTB SVG.gz/package | Fourier R2 | LTTB R2 | coverage | gzip recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smooth | 10000 | 16 | 3 | 27086 | 2.0896 | 5.25138 | 0.0697408 | 0.999838 | 0.998708 | 0.996 | package_preferred_against_gzip |
| smooth | 10000 | 32 | 3 | 27347 | 2.06966 | 5.20127 | 0.0690752 | 0.999923 | 0.998708 | 0.9954 | package_preferred_against_gzip |

## Interpretation Guardrails

- A ratio above `1.0` means the model package is smaller than that baseline.
- LTTB is a downsampling baseline, not a package format; its SVG ratio estimates the size after exporting sampled points as a path.
- Higher R2 alone is not enough. The package must also pass source verification and size evidence checks.
