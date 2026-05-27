# Defensible Compression Research Report

- Terms: `[16]`
- Rows: `6`
- Gate config: `R2 >= 0.99` `leakage <= 0.4` `adaptive_keep <= 0.45` `locality_mode = strict` `include_poly = True`

| dataset | terms | global R2 | detrended R2 | piecewise R2 | poly R2 | global leak | detrended leak | piecewise leak | poly leak | r2-delta | adaptive keep | adaptive th mean | global CR | detrended CR | piecewise CR | poly CR | rdp-pre CR | locality candidates | defensible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| steps | 16 | 0.982742 | 0.982826 | 0.995557 | 0.831637 | 0.426375 | 0.42195 | 0.833125 | 1.05879 | 8.36688e-05 | 0.03825 | 0.0820756 | 163.265 | 156.863 | 153.846 | 181.818 | 11.1421 | 0.833125, 0.42195, 1.05879 | fail |
| spikes | 16 | 0.949117 | 0.947025 | 0.908575 | 0.184617 | 0.845829 | 0.845713 | 0.867483 | 1.00851 | -0.00209163 | 0.021 | 0.273927 | 163.265 | 156.863 | 186.047 | 333.333 | 11.0957 | 0.867483, 0.845713, 1.00851 | fail |
| irregular | 16 | 0.999762 | 0.999183 | 0.94123 | 0.206554 | 0.837811 | 0.779391 | 0.987175 | 1.00456 | -0.000578616 | 0.03 | 0.0207779 | 163.265 | 156.863 | 186.047 | 333.333 | 11.0957 | 0.987175, 0.779391, 1.00456 | fail |
| multiscale | 16 | 0.999685 | 0.99578 | 0.968719 | 0.42933 | 0.993808 | 1.06093 | 0.944989 | 1.01188 | -0.00390578 | 0.04025 | 0.040946 | 163.265 | 156.863 | 153.846 | 181.818 | 11.0957 | 0.944989, 1.06093, 1.01188 | fail |
| smooth | 16 | 0.99978 | 0.999178 | 0.941127 | 0.206671 | 0.826172 | 0.784064 | 0.991277 | 1.00896 | -0.000601417 | 0.032 | 0.0189595 | 163.265 | 156.863 | 186.047 | 333.333 | 11.1421 | 0.991277, 0.784064, 1.00896 | fail |

## Multichannel summary

- rank = 2
- rmse = 0.0528115
- defensible rows = 0 / 6
- dataset pass summary:
  - channels_multiaxis: 0 / 1
  - irregular: 0 / 1
  - multiscale: 0 / 1
  - smooth: 0 / 1
  - spikes: 0 / 1
  - steps: 0 / 1