# Terms x Channel-K x Threshold x Kind Sweep

## Parameters
- Synthetic kinds: `['noisy', 'spikes']`
- Sample sizes: `[5000]`
- Fourier terms: `[32, 64]`
- Channel-K values: `[2.0, 3.0, 4.0]`
- Thresholds: `[0.9, 0.95]`
- RDP epsilon: `0.6`
- SVG samples: `240`

## Global sweep
| threshold | high-fidelity | defensible | defensible ratio | best gzip ratio | best defensible ratio | gate ok |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9 | 0 | 0 | 0% | 1.03674 | n/a | yes |
| 0.95 | 0 | 0 | 0% | 1.03674 | n/a | yes |

## Per-kind stability

| threshold | kind | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0.9 | noisy | 0 | 0 | 0% | 1.03674 | n/a |
| 0.9 | spikes | 0 | 0 | 0% | 0.931394 | n/a |
| 0.95 | noisy | 0 | 0 | 0% | 1.03674 | n/a |
| 0.95 | spikes | 0 | 0 | 0% | 0.931394 | n/a |

## Top cells by threshold

| threshold | term | K | best samples | best ratio |
| ---: | ---: | ---: | ---: | ---: |
| 0.9 | 32 | 4.0 | 5000 | 1.03674 |
| 0.95 | 32 | 4.0 | 5000 | 1.03674 |

## Gate outcomes
| threshold | ok | errors |
| ---: | ---: | --- |
| 0.9 | yes | pass |
| 0.95 | yes | pass |