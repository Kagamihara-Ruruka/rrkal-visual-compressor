# 架構

## 邊界

這個 repository 負責 compression 與 export engine。它不負責 UI state、RRKAL dataset discovery，也不負責 runtime-specific rendering。

```text
Input data
  -> Analyzer
  -> Compressor
  -> VisualModel
  -> Exporter
```

## 主要概念

### Analyzer

Analyzer 檢查輸入資料並記錄基本性質：

- row count
- value ranges
- sampling regularity
- missing values
- candidate methods

MVP analyzer 只需要支援 time series。

目前 analyzer 會輸出 `TimeSeriesProfile`，內容包含 sample count、x/y range、step statistics、uniform-sampling detection、non-finite counts。這份 profile 會被放進 CLI metrics 與 `.vizasset` manifest，讓後續 agent 不需要重讀 raw data 也能做策略判斷。

### Cleaning And Residuals

Cleaning 被視為可追溯的 lineage step：

```text
raw series -> cleaned main series
raw series - cleaned main series -> residual layer candidate
```

第一批 cleaning operators 是 moving-average smoothing 與 global sigma clipping。它們不會修改 raw series。Residual analyzer 會把剩餘層分類為 sparse outliers、Fourier-friendly residual、statistical noise，或沒有 meaningful residual。這可以避免「去噪」預設變成資料遺失。

Residual storage 依分類決定：

- sparse outliers 存成 sparse `(index, x, delta_y)` points。
- Fourier-friendly residuals 存成 secondary Fourier layer。
- statistical noise 預設只摘要，除非 caller 明確要求保存。

### Compressor

Compressor 把資料轉成 compact model。

初始 compressors：

- `RDPCompressor`：保留 visually important polyline points。
- `FourierCompressor`：保留 high-energy frequency coefficients。

未來 compressors：

- spline
- wavelet
- contour
- cluster hull
- Bezier fitting

### VisualModel

VisualModel 是 compression 與 export 之間的穩定中介表示。

它應該攜帶：

- model type
- input summary
- model parameters 或 external parameter files
- style defaults
- reconstruction hints
- metrics

它不應該依賴 Qt、Matplotlib 或 RRKAL。

### Exporter

Exporter 把 `VisualModel` 輸出成 target artifacts：

- SVG
- SVGZ
- PNG preview
- `demo.py`
- `metrics.json`
- package folder

### `.vizasset`

Package folder 是 compressor、RRKAL、editor 之間第一個穩定 handoff contract。它保存 compact reconstruction data 與 generated previews，不保存 raw source data。

```text
model.vizretain/
  asset.json
  model.npz
  preview.svg
  metrics.json
  demo.py
```

`asset.json` 記錄 schema version、source summary、method metadata、metrics、file sizes、file checksums、lineage notes。`model.npz` 儲存 compact model parameters，例如 RDP points、Fourier coefficients、optional channel band points。

Package family 有幾個 profile suffix：

- `.vizretain`：保存 residual/noise layers。
- `.vizclean`：只輸出 cleaned main signal，即使 build report 算過 residual。
- `.vizasset`：中性名稱，供相容與手動流程使用。

Package module 可以讀回 renderable arrays：

- `reconstruct_fourier(package, samples=...)`
- `reconstruct_channel(package, samples=...)`
- `reconstruct_retained_signal(package, samples=...)`
- `validate_vizasset(package, reconstruction_samples=...)`

目前 domain reconstruction 支援：

- uniform time series：`linspace_from_min_max`
- irregular time axis：保存完整 `x_values`
- compressed irregular domain：`linear_plus_rdp_delta`

Package verification 遵守 RRKAL-style 原則：generated assets 必須能被機器檢查。`vizcompress verify` 會檢查 manifest shape、必要檔案、byte sizes、SHA-256 hashes、`model.npz` arrays、x-domain consistency、residual layer array consistency，以及 finite reconstruction。這不證明 package 是全球最佳壓縮；它證明 package 的 handoff 足夠自洽，editor 或 renderer 可以信任。

如果 source dataset 還在，`vizcompress verify` 也可以做 source-backed fidelity verification：decode package 後，在明確 RMSE/MAE/max-error budget 下跟原始 source 比較。這是專案核心公式的 runtime 版本：

```math
\epsilon(D, decode(P)) \leq \tau
```

`review.json` 是 `--review-packet` 產生的 optional sidecar。它記錄 source fingerprints、verification policy、package self-check、source-fidelity metrics，以及最後的 accepted flag。它用於 RRKAL/editor handoff 與後續 audit，不用來重建 visual model。

## Export Modes

### Pure SVG

相容性最好。直接保存 paths/shapes。

### Hybrid SVG

重資料層用 raster image，axes、annotations、labels 仍保留 vector elements。

### Model-backed SVG

把 compressed parameters 存在 metadata 或 script。可能更小，但設計工具不一定支援。

## Sweet Spot

專案應該 benchmark break-even points，而不是宣稱 universal superiority。

```text
model_size + overhead < direct_svg_size_at_same_error
```

有用的輸出是一條曲線：

```text
file size vs fidelity
```

不是單一魔法門檻。

`bench` command 是這個想法的第一個實作。它比較：

```text
direct SVG bytes
  vs
model-backed .vizasset bytes
```

用 synthetic sample-size sweep 讓 Big-O 討論變得可量測：direct SVG 隨 sampled point count 成長，而 model-backed package 主要隨 model parameters、固定 preview resolution、metadata 成長。

Benchmark recommendations 由 `vizcompress.selectors` 產生，之後 build-time automatic method selection 也可以重用同一套 decision rules。
