# Defensible Threshold Sweep

## Parameters
- Synthetic kind: `smooth`
- Sample sizes: `[10000]`
- Fourier terms: `16`
- Channel K: `3.0`
- Channel window: `16`
- Channel band epsilon: `0.04`
- SVG samples: `240`

This sweep is intended to show the fragility of coverage-based defensibility. A high best size ratio is only adopted when the defensible sample count and ratio are also acceptable.

## Sweep

| threshold | high-fidelity | defensible | defensible ratio | best SVG.gz | best defensible SVG.gz | best high-fidelity SVG.gz |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.8 | 1 | 0 | 0% | 2.27625 | n/a | 2.27625 |
| 0.9 | 1 | 0 | 0% | 2.27625 | n/a | 2.27625 |
| 0.95 | 1 | 0 | 0% | 2.27625 | n/a | 2.27625 |
| 0.98 | 1 | 0 | 0% | 2.27625 | n/a | 2.27625 |
| 0.995 | 1 | 0 | 0% | 2.27625 | n/a | 2.27625 |

## Interpretation

This sweep is intended to show the fragility of coverage-based defensibility. A high best size ratio is only adopted when the defensible sample count and ratio are also acceptable.