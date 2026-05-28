# Defensible Compression Research Report

- Terms: `[16, 32, 64]`
- Rows: `16`
- Gate config: `R2 >= 0.99` `leakage <= 0.25` `adaptive_keep <= 0.45` `locality_mode = strict` `include_poly = True`

| dataset | terms | global R2 | detrended R2 | piecewise R2 | poly R2 | global leak | detrended leak | piecewise leak | poly leak | r2-delta | adaptive keep | adaptive th mean | global CR | detrended CR | piecewise CR | poly CR | rdp-pre CR | locality candidates | defensible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| steps | 16 | 0.982742 | 0.982826 | 0.995557 | 0.831637 | 0.426375 | 0.42195 | 0.833125 | 1.05879 | 8.36688e-05 | 0.03825 | 0.0820756 | 163.265 | 156.863 | 153.846 | 181.818 | 11.1421 | 0.833125, 0.42195, 1.05879 | fail |
| steps | 32 | 0.991292 | 0.991183 | 0.998126 | 0.831637 | 0.429123 | 0.400856 | 0.77408 | 1.05879 | -0.000109425 | 0.0205 | 0.0667293 | 82.4742 | 80.8081 | 80 | 181.818 | 8.32466 | 0.77408, 0.400856, 1.05879 | fail |
| steps | 64 | 0.995604 | 0.995596 | 0.999055 | 0.831637 | 0.39212 | 0.417853 | 0.724723 | 1.05879 | -8.18487e-06 | 0.0155 | 0.0514839 | 41.4508 | 41.0256 | 43.4783 | 181.818 | 5.5517 | 0.724723, 0.417853, 1.05879 | fail |
| spikes | 16 | 0.949117 | 0.947025 | 0.908575 | 0.184617 | 0.845829 | 0.845713 | 0.867483 | 1.00851 | -0.00209163 | 0.021 | 0.273927 | 163.265 | 156.863 | 186.047 | 333.333 | 11.0957 | 0.867483, 0.845713, 1.00851 | fail |
| spikes | 32 | 0.968152 | 0.96732 | 0.943187 | 0.184617 | 0.824216 | 0.810956 | 0.843799 | 1.00851 | -0.000832832 | 0.01425 | 0.22395 | 82.4742 | 80.8081 | 109.589 | 333.333 | 8.32466 | 0.843799, 0.810956, 1.00851 | fail |
| spikes | 64 | 0.98713 | 0.98703 | 0.971917 | 0.184617 | 0.759185 | 0.77061 | 0.823654 | 1.00851 | -0.000100588 | 0.018 | 0.141165 | 41.4508 | 41.0256 | 57.554 | 333.333 | 5.5517 | 0.823654, 0.77061, 1.00851 | fail |
| irregular | 16 | 0.999762 | 0.999183 | 0.94123 | 0.206554 | 0.837811 | 0.779391 | 0.987175 | 1.00456 | -0.000578616 | 0.03 | 0.0207779 | 163.265 | 156.863 | 186.047 | 333.333 | 11.0957 | 0.987175, 0.779391, 1.00456 | fail |
| irregular | 32 | 0.999897 | 0.999557 | 0.986744 | 0.206554 | 0.772311 | 0.774708 | 0.967011 | 1.00456 | -0.000339896 | 0.029 | 0.0143829 | 82.4742 | 80.8081 | 109.589 | 333.333 | 8.32466 | 0.967011, 0.774708, 1.00456 | fail |
| irregular | 64 | 0.99995 | 0.999787 | 0.997392 | 0.206554 | 0.760319 | 0.751485 | 0.921611 | 1.00456 | -0.000162544 | 0.024 | 0.00866526 | 41.4508 | 41.0256 | 57.554 | 333.333 | 5.5517 | 0.921611, 0.751485, 1.00456 | fail |
| multiscale | 16 | 0.999685 | 0.99578 | 0.968719 | 0.42933 | 0.993808 | 1.06093 | 0.944989 | 1.01188 | -0.00390578 | 0.04025 | 0.040946 | 163.265 | 156.863 | 153.846 | 181.818 | 11.0957 | 0.944989, 1.06093, 1.01188 | fail |
| multiscale | 32 | 0.999844 | 0.997879 | 0.987513 | 0.42933 | 1.05173 | 1.07507 | 0.838633 | 1.01188 | -0.00196478 | 0.0365 | 0.0263187 | 82.4742 | 80.8081 | 80 | 181.818 | 8.32466 | 0.838633, 1.07507, 1.01188 | fail |
| multiscale | 64 | 0.999923 | 0.998937 | 0.995315 | 0.42933 | 1.07561 | 1.07746 | 0.687435 | 1.01188 | -0.000985946 | 0.03425 | 0.0163781 | 41.4508 | 41.0256 | 43.4783 | 181.818 | 5.56328 | 0.687435, 1.07746, 1.01188 | fail |
| smooth | 16 | 0.99978 | 0.999178 | 0.941127 | 0.206671 | 0.826172 | 0.784064 | 0.991277 | 1.00896 | -0.000601417 | 0.032 | 0.0189595 | 163.265 | 156.863 | 186.047 | 333.333 | 11.1421 | 0.991277, 0.784064, 1.00896 | fail |
| smooth | 32 | 0.9999 | 0.999567 | 0.986814 | 0.206671 | 0.775967 | 0.779866 | 0.980124 | 1.00896 | -0.000333535 | 0.0365 | 0.0120162 | 82.4742 | 80.8081 | 109.589 | 333.333 | 8.35073 | 0.980124, 0.779866, 1.00896 | fail |
| smooth | 64 | 0.99995 | 0.999787 | 0.997418 | 0.206671 | 0.775616 | 0.762532 | 0.934696 | 1.00896 | -0.000163414 | 0.0335 | 0.00762713 | 41.4508 | 41.0256 | 57.554 | 333.333 | 5.5517 | 0.934696, 0.762532, 1.00896 | fail |

## Multichannel summary

- rank = 2
- rmse = 0.0528115
- defensible rows = 0 / 16
- dataset pass summary:
  - channels_multiaxis: 0 / 1
  - irregular: 0 / 3
  - multiscale: 0 / 3
  - smooth: 0 / 3
  - spikes: 0 / 3
  - steps: 0 / 3

## Local strategy probe

- probe counts:
  - sparse_residual_layer: 15
- best Haar R2 delta vs RDP = `-1.82865`
- best adaptive residual payload ratio = `70.1754`

| dataset | terms | recommended probe | Haar R2 delta vs RDP | Haar CR delta vs RDP | adaptive keep | adaptive CR |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| steps | 16 | sparse_residual_layer | -2.50542 | -0.643374 | 0.03825 | 26.1438 |
| steps | 32 | sparse_residual_layer | -2.51865 | 2.17403 | 0.0205 | 48.7805 |
| steps | 64 | sparse_residual_layer | -2.52604 | 4.94699 | 0.0155 | 64.5161 |
| spikes | 16 | sparse_residual_layer | -1.94438 | 0.669005 | 0.021 | 47.619 |
| spikes | 32 | sparse_residual_layer | -1.97863 | 3.44004 | 0.01425 | 70.1754 |
| spikes | 64 | sparse_residual_layer | -2.01374 | 6.21301 | 0.018 | 55.5556 |
| irregular | 16 | sparse_residual_layer | -1.94375 | 0.51533 | 0.03 | 33.3333 |
| irregular | 32 | sparse_residual_layer | -1.9562 | 3.28637 | 0.029 | 34.4828 |
| irregular | 64 | sparse_residual_layer | -1.97542 | 6.05933 | 0.024 | 41.6667 |
| multiscale | 16 | sparse_residual_layer | -1.82865 | -1.60578 | 0.04025 | 24.8447 |
| multiscale | 32 | sparse_residual_layer | -1.86564 | 1.16526 | 0.0365 | 27.3973 |
| multiscale | 64 | sparse_residual_layer | -1.89735 | 3.92663 | 0.03425 | 29.1971 |
| smooth | 16 | sparse_residual_layer | -1.94357 | 0.452142 | 0.032 | 31.25 |
| smooth | 32 | sparse_residual_layer | -1.96348 | 3.24347 | 0.0365 | 27.3973 |
| smooth | 64 | sparse_residual_layer | -1.9765 | 6.0425 | 0.0335 | 29.8507 |

### Sparse residual frontier

- best R2 delta vs base = `0.0367638`
- best payload ratio = `20`
- promotable rows = `13`

| dataset | terms | keep ratio | keep count | R2 | R2 delta vs base | payload ratio | promotable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| steps | 16 | 0.05 | 200 | 0.997107 | 0.0142818 | 20 | yes |
| steps | 32 | 0.05 | 200 | 0.998648 | 0.00746486 | 20 | yes |
| steps | 64 | 0.05 | 200 | 0.999584 | 0.00398798 | 20 | yes |
| spikes | 16 | 0.05 | 200 | 0.983789 | 0.0367638 | 20 | no |
| spikes | 32 | 0.05 | 200 | 0.988748 | 0.0214286 | 20 | no |
| spikes | 64 | 0.05 | 200 | 0.995453 | 0.00842308 | 20 | yes |
| irregular | 16 | 0.05 | 200 | 0.99986 | 0.000677002 | 20 | yes |
| irregular | 32 | 0.05 | 200 | 0.999942 | 0.000385108 | 20 | yes |
| irregular | 64 | 0.05 | 200 | 0.999984 | 0.000196946 | 20 | yes |
| multiscale | 16 | 0.05 | 200 | 0.999014 | 0.00323392 | 20 | yes |
| multiscale | 32 | 0.05 | 200 | 0.999665 | 0.00178578 | 20 | yes |
| multiscale | 64 | 0.05 | 200 | 0.999909 | 0.000971923 | 20 | yes |
| smooth | 16 | 0.05 | 200 | 0.999879 | 0.000700919 | 20 | yes |
| smooth | 32 | 0.05 | 200 | 0.999961 | 0.000393916 | 20 | yes |
| smooth | 64 | 0.05 | 200 | 0.999988 | 0.000201229 | 20 | yes |

### Sparse residual escalation

- promotable rows = `15`
- solved by escalation = `2`
- budget tiers = `{'cheap_residual': 0, 'moderate_residual': 1, 'expensive_residual': 1}`
- recommended strategy = `raise_terms_or_localize_before_promoting_residual`
- rationale: some rows need more than 10% residual retention, so residuals are acting like a large side channel
- term-sensitivity improvements = `1`

| dataset | terms | minimum keep ratio | budget tier | R2 | payload ratio |
| --- | ---: | ---: | --- | ---: | ---: |
| spikes | 16 | 0.2 | expensive_residual | 0.99197 | 5 |
| spikes | 32 | 0.1 | moderate_residual | 0.992156 | 10 |

| dataset | from terms | to terms | keep ratio delta | budget tier change |
| --- | ---: | ---: | ---: | --- |
| spikes | 16 | 32 | -0.1 | expensive_residual -> moderate_residual |

- frontier strict gate = 0.99
- frontier exploratory gate = 0.95
- frontier demo gate = 0.9
- frontier best-point tiers:
  - demo_pass: 3
  - exploratory_pass: 8
  - strict_pass: 4

### RDP frontier tier matrix

| exploratory gate | demo gate | strict | exploratory | demo | reject | payload reject | best R2 | best payload ratio |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.94 | 0.88 | 4 | 10 | 1 | 0 | 0 | 0.999917 | 18.4758 |
| 0.94 | 0.9 | 4 | 10 | 1 | 0 | 0 | 0.999917 | 18.4758 |
| 0.94 | 0.92 | 4 | 10 | 1 | 0 | 0 | 0.999917 | 18.4758 |
| 0.94 | 0.94 | 4 | 10 | 0 | 1 | 0 | 0.999917 | 18.8679 |
| 0.95 | 0.88 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.95 | 0.9 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.95 | 0.92 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.95 | 0.94 | 4 | 8 | 2 | 1 | 0 | 0.999917 | 18.8679 |
| 0.96 | 0.88 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.96 | 0.9 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.96 | 0.92 | 4 | 8 | 3 | 0 | 0 | 0.999917 | 18.4758 |
| 0.96 | 0.94 | 4 | 8 | 2 | 1 | 0 | 0.999917 | 18.8679 |
| 0.97 | 0.88 | 4 | 7 | 4 | 0 | 0 | 0.999917 | 18.4758 |
| 0.97 | 0.9 | 4 | 7 | 4 | 0 | 0 | 0.999917 | 18.4758 |
| 0.97 | 0.92 | 4 | 7 | 4 | 0 | 0 | 0.999917 | 18.4758 |
| 0.97 | 0.94 | 4 | 7 | 3 | 1 | 0 | 0.999917 | 18.8679 |

## RDP frontier scan

| dataset | terms | target keep ratio | actual keep | r2 | payload ratio | kept points | best gate reason | frontier tier | best under R2 gate? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |
| steps | 16 | 0.02 | 0.032 | 0.974827 | 18.4758 | 128 | r2_below_gate | exploratory_pass | no |
| steps | 32 | 0.02 | 0.032 | 0.99335 | 16.632 | 128 | pass | strict_pass | yes |
| steps | 64 | 0.02 | 0.032 | 0.999917 | 13.8648 | 128 | pass | strict_pass | yes |
| spikes | 16 | 0.05 | 0.05 | 0.913016 | 12.3267 | 200 | r2_below_gate | demo_pass | no |
| spikes | 32 | 0.02 | 0.03125 | 0.942901 | 16.9492 | 125 | r2_below_gate | demo_pass | no |
| spikes | 64 | 0.02 | 0.03125 | 0.982078 | 14.1593 | 125 | r2_below_gate | exploratory_pass | no |
| irregular | 16 | 0.05 | 0.05 | 0.959122 | 12.3267 | 200 | r2_below_gate | exploratory_pass | no |
| irregular | 32 | 0.02 | 0.032 | 0.968719 | 16.632 | 128 | r2_below_gate | exploratory_pass | no |
| irregular | 64 | 0.05 | 0.05 | 0.992914 | 10.0883 | 200 | pass | strict_pass | yes |
| multiscale | 16 | 0.02 | 0.032 | 0.901833 | 18.4758 | 128 | r2_below_gate | demo_pass | no |
| multiscale | 32 | 0.1 | 0.09925 | 0.962806 | 6.21118 | 397 | r2_below_gate | exploratory_pass | no |
| multiscale | 64 | 0.1 | 0.09925 | 0.970111 | 5.78035 | 397 | r2_below_gate | exploratory_pass | no |
| smooth | 16 | 0.05 | 0.05 | 0.96087 | 12.3267 | 200 | r2_below_gate | exploratory_pass | no |
| smooth | 32 | 0.02 | 0.032 | 0.968669 | 16.632 | 128 | r2_below_gate | exploratory_pass | no |
| smooth | 64 | 0.05 | 0.05 | 0.99241 | 10.0883 | 200 | pass | strict_pass | yes |

- noise frontier best-point tiers:
  - demo_pass: 16
  - exploratory_pass: 14
  - payload_reject: 0
  - reject: 5
  - strict_pass: 1

### Noise frontier recommendation

- recommended strategy: `sparse_residual_layer`
- rationale: spike-like data fails before smooth data, so sparse residual handling should be promoted
- worst kind: `spikes`
- high-sigma reject ratio: `0.222222`

### Noise frontier tier matrix

| exploratory gate | demo gate | strict | exploratory | demo | reject | payload reject | best R2 | best payload ratio |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.94 | 0.88 | 1 | 21 | 11 | 3 | 0 | 0.99241 | 18.6047 |
| 0.94 | 0.9 | 1 | 21 | 9 | 5 | 0 | 0.99241 | 18.6047 |
| 0.94 | 0.92 | 1 | 21 | 4 | 10 | 0 | 0.99241 | 18.6047 |
| 0.94 | 0.94 | 1 | 21 | 0 | 14 | 0 | 0.99241 | 18.8679 |
| 0.95 | 0.88 | 1 | 14 | 18 | 3 | 0 | 0.99241 | 18.6047 |
| 0.95 | 0.9 | 1 | 14 | 16 | 5 | 0 | 0.99241 | 18.6047 |
| 0.95 | 0.92 | 1 | 14 | 11 | 10 | 0 | 0.99241 | 18.6047 |
| 0.95 | 0.94 | 1 | 14 | 7 | 14 | 0 | 0.99241 | 18.8679 |
| 0.96 | 0.88 | 1 | 11 | 21 | 3 | 0 | 0.99241 | 18.6047 |
| 0.96 | 0.9 | 1 | 11 | 19 | 5 | 0 | 0.99241 | 18.6047 |
| 0.96 | 0.92 | 1 | 11 | 14 | 10 | 0 | 0.99241 | 18.6047 |
| 0.96 | 0.94 | 1 | 11 | 10 | 14 | 0 | 0.99241 | 18.8679 |
| 0.97 | 0.88 | 1 | 8 | 24 | 3 | 0 | 0.99241 | 18.6047 |
| 0.97 | 0.9 | 1 | 8 | 22 | 5 | 0 | 0.99241 | 18.6047 |
| 0.97 | 0.92 | 1 | 8 | 17 | 10 | 0 | 0.99241 | 18.6047 |
| 0.97 | 0.94 | 1 | 8 | 13 | 14 | 0 | 0.99241 | 18.8679 |

## Noise frontier scan

| base kind | sigma | terms | target keep ratio | actual keep | r2 | payload ratio | gate reason | frontier tier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| smooth | 0 | 16 | 0.05 | 0.05 | 0.96087 | 12.3267 | r2_below_gate | exploratory_pass |
| smooth | 0 | 32 | 0.02 | 0.032 | 0.968669 | 16.632 | r2_below_gate | exploratory_pass |
| smooth | 0 | 64 | 0.05 | 0.05 | 0.99241 | 10.0883 | pass | strict_pass |
| smooth | 0.02 | 16 | 0.02 | 0.03175 | 0.920406 | 18.6047 | r2_below_gate | demo_pass |
| smooth | 0.02 | 32 | 0.02 | 0.03175 | 0.96626 | 16.7364 | r2_below_gate | exploratory_pass |
| smooth | 0.02 | 64 | 0.02 | 0.03175 | 0.98103 | 13.9373 | r2_below_gate | exploratory_pass |
| smooth | 0.05 | 16 | 0.2 | 0.2 | 0.921343 | 3.26664 | r2_below_gate | demo_pass |
| smooth | 0.05 | 32 | 0.2 | 0.2 | 0.951585 | 3.20384 | r2_below_gate | exploratory_pass |
| smooth | 0.05 | 64 | 0.02 | 0.03175 | 0.950314 | 13.9373 | r2_below_gate | exploratory_pass |
| smooth | 0.1 | 16 | 0.3 | 0.29975 | 0.907266 | 2.19419 | r2_below_gate | demo_pass |
| smooth | 0.1 | 32 | 0.2 | 0.2 | 0.916234 | 3.20384 | r2_below_gate | demo_pass |
| smooth | 0.1 | 64 | 0.1 | 0.1 | 0.902599 | 5.743 | r2_below_gate | demo_pass |
| spikes | 0 | 16 | 0.05 | 0.05 | 0.913016 | 12.3267 | r2_below_gate | demo_pass |
| spikes | 0 | 32 | 0.02 | 0.03125 | 0.942901 | 16.9492 | r2_below_gate | demo_pass |
| spikes | 0 | 64 | 0.02 | 0.03125 | 0.982078 | 14.1593 | r2_below_gate | exploratory_pass |
| spikes | 0.02 | 16 | 0.02 | 0.03175 | 0.883919 | 18.6047 | r2_below_gate | reject |
| spikes | 0.02 | 32 | 0.02 | 0.03175 | 0.944776 | 16.7364 | r2_below_gate | demo_pass |
| spikes | 0.02 | 64 | 0.02 | 0.03175 | 0.977769 | 13.9373 | r2_below_gate | exploratory_pass |
| spikes | 0.05 | 16 | 0.02 | 0.032 | 0.820639 | 18.4758 | r2_below_gate | reject |
| spikes | 0.05 | 32 | 0.02 | 0.032 | 0.914274 | 16.632 | r2_below_gate | demo_pass |
| spikes | 0.05 | 64 | 0.02 | 0.032 | 0.953282 | 13.8648 | r2_below_gate | exploratory_pass |
| spikes | 0.1 | 16 | 0.02 | 0.032 | 0.813989 | 18.4758 | r2_below_gate | reject |
| spikes | 0.1 | 32 | 0.02 | 0.032 | 0.831033 | 16.632 | r2_below_gate | reject |
| spikes | 0.1 | 64 | 0.1 | 0.1 | 0.904307 | 5.743 | r2_below_gate | demo_pass |
| multiscale | 0 | 16 | 0.02 | 0.032 | 0.901833 | 18.4758 | r2_below_gate | demo_pass |
| multiscale | 0 | 32 | 0.1 | 0.09925 | 0.962806 | 6.21118 | r2_below_gate | exploratory_pass |
| multiscale | 0 | 64 | 0.1 | 0.09925 | 0.970111 | 5.78035 | r2_below_gate | exploratory_pass |
| multiscale | 0.02 | 16 | 0.1 | 0.09975 | 0.948845 | 6.42055 | r2_below_gate | demo_pass |
| multiscale | 0.02 | 32 | 0.1 | 0.09975 | 0.960457 | 6.18238 | r2_below_gate | exploratory_pass |
| multiscale | 0.02 | 64 | 0.1 | 0.09975 | 0.964687 | 5.7554 | r2_below_gate | exploratory_pass |
| multiscale | 0.05 | 16 | 0.1 | 0.1 | 0.924311 | 6.40512 | r2_below_gate | demo_pass |
| multiscale | 0.05 | 32 | 0.1 | 0.1 | 0.932809 | 6.16808 | r2_below_gate | demo_pass |
| multiscale | 0.05 | 64 | 0.2 | 0.2 | 0.954373 | 3.08523 | r2_below_gate | exploratory_pass |
| multiscale | 0.1 | 16 | 0.02 | 0.032 | 0.708772 | 18.4758 | r2_below_gate | reject |
| multiscale | 0.1 | 32 | 0.3 | 0.29975 | 0.901202 | 2.16567 | r2_below_gate | demo_pass |
| multiscale | 0.1 | 64 | 0.3 | 0.29975 | 0.912608 | 2.11082 | r2_below_gate | demo_pass |

### Noise frontier by sigma

| sigma | rows | gate passes | strict | exploratory | demo | reject | payload reject | monotonic rows | best R2 | best payload ratio |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 9 | 1 | 1 | 5 | 3 | 0 | 0 | 9 | 0.99241 | 18.4758 |
| 0.02 | 9 | 0 | 0 | 5 | 3 | 1 | 0 | 9 | 0.98103 | 18.6047 |
| 0.05 | 9 | 0 | 0 | 4 | 4 | 1 | 0 | 9 | 0.954373 | 18.4758 |
| 0.1 | 9 | 0 | 0 | 0 | 6 | 3 | 0 | 9 | 0.916234 | 18.4758 |

### Noise frontier by kind

| kind | rows | gate passes | strict | exploratory | demo | reject | payload reject | monotonic rows | best R2 | best payload ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiscale | 12 | 0 | 0 | 5 | 6 | 1 | 0 | 12 | 0.970111 | 18.4758 |
| smooth | 12 | 1 | 1 | 6 | 5 | 0 | 0 | 12 | 0.99241 | 18.6047 |
| spikes | 12 | 0 | 0 | 3 | 5 | 4 | 0 | 12 | 0.982078 | 18.6047 |