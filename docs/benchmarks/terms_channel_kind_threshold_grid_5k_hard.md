# Terms x Channel-K x Threshold x Kind Sweep

## Parameters
- Synthetic kinds: `['noisy', 'spikes', 'steps']`
- Sample sizes: `[5000]`
- Fourier terms: `[16, 32, 64]`
- Channel-K values: `[2.0, 3.0, 4.0]`
- Thresholds: `[0.9, 0.95, 0.98]`
- RDP epsilon: `0.6`
- SVG samples: `240`

## Global sweep
| threshold | high-fidelity | defensible | defensible ratio | best gzip ratio | best defensible ratio | gate ok |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9 | 6 | 0 | 0% | 1.16649 | n/a | yes |
| 0.95 | 6 | 0 | 0% | 1.16649 | n/a | yes |
| 0.98 | 6 | 0 | 0% | 1.16649 | n/a | yes |

## Per-kind stability

| threshold | kind | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0.9 | noisy | 0 | 0 | 0% | 1.14074 | n/a |
| 0.9 | spikes | 0 | 0 | 0% | 1.13111 | n/a |
| 0.9 | steps | 6 | 0 | 0% | 1.16649 | n/a |
| 0.95 | noisy | 0 | 0 | 0% | 1.14074 | n/a |
| 0.95 | spikes | 0 | 0 | 0% | 1.13111 | n/a |
| 0.95 | steps | 6 | 0 | 0% | 1.16649 | n/a |
| 0.98 | noisy | 0 | 0 | 0% | 1.14074 | n/a |
| 0.98 | spikes | 0 | 0 | 0% | 1.13111 | n/a |
| 0.98 | steps | 6 | 0 | 0% | 1.16649 | n/a |

## Top cells by threshold

| threshold | term | K | best samples | best ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.9 | 16 | 2.0 | 5000 | 1.16649 |
| 0.95 | 16 | 2.0 | 5000 | 1.16649 |
| 0.98 | 16 | 2.0 | 5000 | 1.16649 |

## Gate outcomes
| threshold | ok | errors |
| ---: | ---: | --- |
| 0.9 | yes | pass |
| 0.95 | yes | pass |
| 0.98 | yes | pass |