# Fourier Terms x Channel-K Sweep

## Parameters
- Sample sizes: `[10000]`
- Fourier terms: `[16, 32]`
- Channel K values: `[2.0, 3.0]`
- RDP epsilon: `0.6`
- SVG samples: `240`
- Defensible threshold: `0.9`

## High-level
- Overall best SVG.gz ratio: `2.27634`
- High-fidelity rows: `4`
- Defensible rows: `0 (0%)`
- Best defensible row: `16|2`

## Grid summary

| term | K | samples | gzip ratio | high-fidelity | defensible | coverage | channel rows |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 2 | 10000 | 2.27634 | 1 | 0 | 0 | 24864 |
| 16 | 3 | 10000 | 2.27625 | 1 | 0 | 0 | 24865 |
| 32 | 2 | 10000 | 2.24546 | 1 | 0 | 0 | 25206 |
| 32 | 3 | 10000 | 2.2451 | 1 | 0 | 0 | 25210 |

## Execution policy
- If `defensible_rows_count=0`, high compressibility did not remain stable under the defended threshold.
- Compare `best_rows.direct_svg_gzip.ratio` and `best_defensible...` in raw JSON for precise policy choice.