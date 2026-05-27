# Fourier Terms x Channel-K vs Defensible Threshold Sweep

## Parameters
- Sample sizes: `[10000]`
- Fourier terms: `[16, 32]`
- Channel-K values: `[2.0, 3.0, 4.0]`
- Thresholds: `[0.9, 0.92, 0.95, 0.98]`
- RDP epsilon: `0.6`
- SVG samples: `240`

## Sweep (global summary)
| threshold | high-fidelity | defensible | defensible ratio | best SVG.gz | best defensible SVG.gz |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9 | 6 | 0 | 0% | 2.27634 | n/a |
| 0.92 | 6 | 0 | 0% | 2.27634 | n/a |
| 0.95 | 6 | 0 | 0% | 2.27634 | n/a |
| 0.98 | 6 | 0 | 0% | 2.27634 | n/a |

## Cell summary

| term | K | threshold | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio | defensible exists |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 2 | 0.9 | 1 | 0 | 0% | 2.27634 | n/a | no |
| 16 | 3 | 0.9 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 16 | 4 | 0.9 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 32 | 2 | 0.9 | 1 | 0 | 0% | 2.24546 | n/a | no |
| 32 | 3 | 0.9 | 1 | 0 | 0% | 2.2451 | n/a | no |
| 32 | 4 | 0.9 | 1 | 0 | 0% | 2.24537 | n/a | no |
| 16 | 2 | 0.92 | 1 | 0 | 0% | 2.27634 | n/a | no |
| 16 | 3 | 0.92 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 16 | 4 | 0.92 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 32 | 2 | 0.92 | 1 | 0 | 0% | 2.24546 | n/a | no |
| 32 | 3 | 0.92 | 1 | 0 | 0% | 2.2451 | n/a | no |
| 32 | 4 | 0.92 | 1 | 0 | 0% | 2.24537 | n/a | no |
| 16 | 2 | 0.95 | 1 | 0 | 0% | 2.27634 | n/a | no |
| 16 | 3 | 0.95 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 16 | 4 | 0.95 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 32 | 2 | 0.95 | 1 | 0 | 0% | 2.24546 | n/a | no |
| 32 | 3 | 0.95 | 1 | 0 | 0% | 2.2451 | n/a | no |
| 32 | 4 | 0.95 | 1 | 0 | 0% | 2.24537 | n/a | no |
| 16 | 2 | 0.98 | 1 | 0 | 0% | 2.27634 | n/a | no |
| 16 | 3 | 0.98 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 16 | 4 | 0.98 | 1 | 0 | 0% | 2.27625 | n/a | no |
| 32 | 2 | 0.98 | 1 | 0 | 0% | 2.24546 | n/a | no |
| 32 | 3 | 0.98 | 1 | 0 | 0% | 2.2451 | n/a | no |
| 32 | 4 | 0.98 | 1 | 0 | 0% | 2.24537 | n/a | no |