# Terms x Channel-K x Threshold x Kind Sweep

## Parameters
- Synthetic kinds: `['chirp', 'irregular', 'multiscale', 'noisy', 'smooth', 'spikes', 'steps']`
- Sample sizes: `[10000]`
- Fourier terms: `[16, 32]`
- Channel-K values: `[2.0, 3.0, 4.0]`
- Thresholds: `[0.9, 0.98]`
- RDP epsilon: `0.6`
- SVG samples: `240`

## Global sweep
| threshold | high-fidelity | defensible | defensible ratio | best gzip ratio | best defensible ratio | gate ok |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9 | 21 | 3 | 14.2857% | 2.28007 | 2.28007 | no |
| 0.98 | 21 | 0 | 0% | 2.28007 | n/a | no |

## Per-kind stability

| threshold | kind | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0.9 | chirp | 0 | 0 | 0% | 2.20173 | n/a |
| 0.9 | irregular | 6 | 0 | 0% | 0.573735 | n/a |
| 0.9 | multiscale | 6 | 3 | 50% | 2.28007 | n/a |
| 0.9 | noisy | 0 | 0 | 0% | 2.19246 | n/a |
| 0.9 | smooth | 6 | 0 | 0% | 2.27634 | n/a |
| 0.9 | spikes | 0 | 0 | 0% | 2.19347 | n/a |
| 0.9 | steps | 3 | 0 | 0% | 2.25784 | n/a |
| 0.98 | chirp | 0 | 0 | 0% | 2.20173 | n/a |
| 0.98 | irregular | 6 | 0 | 0% | 0.573735 | n/a |
| 0.98 | multiscale | 6 | 0 | 0% | 2.28007 | n/a |
| 0.98 | noisy | 0 | 0 | 0% | 2.19246 | n/a |
| 0.98 | smooth | 6 | 0 | 0% | 2.27634 | n/a |
| 0.98 | spikes | 0 | 0 | 0% | 2.19347 | n/a |
| 0.98 | steps | 3 | 0 | 0% | 2.25784 | n/a |

## Top cells by threshold

| threshold | term | K | best samples | best ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.9 | 16 | 3.0 | 10000 | 2.28007 |
| 0.98 | 16 | 3.0 | 10000 | 2.28007 |

## Gate outcomes
| threshold | ok | errors |
| ---: | ---: | --- |
| 0.9 | no | package did not beat SVG.gz in any benchmark row; defensible ratio 0.1429 below minimum 0.2000 |
| 0.98 | no | package did not beat SVG.gz in any benchmark row; defensible ratio 0.0000 below minimum 0.2000 |