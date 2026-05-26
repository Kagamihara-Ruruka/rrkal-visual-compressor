# Roadmap

這個專案應該從狹窄、可測試的 compression engine，逐步長成 geometry-aware visual modeling system。第一原則是控制範圍：先證明一種資料，再加入下一種。

## 核心論點

傳統 SVG 會讓 visual complexity 綁死 raw sample count：

```text
N samples -> O(N) path/circle output
```

本專案希望讓 visual complexity 綁定 model complexity：

```text
N samples -> O(A + K + T) visual model
```

其中：

- `A`：anchors，例如 center、focus points、skeleton points。
- `K`：function parameters，例如 Fourier coefficients 或 spline knots。
- `T`：topology metadata，例如 open/closed、holes、components、boundaries。

SVG 是 export target。Compressed visual model 才是 source of truth。

## Phase 0: Proof Migration

目標：把既有 proof 搬進 tested library modules。

Tasks：

- 把 RDP、Fourier reconstruction、SVG path writing、metrics 搬到 `src/vizcompress/`。
- 加入 synthetic time-series fixture generation。
- 加入 time-series analyzer profiles。
- 加入 import、RDP、Fourier、metrics、SVG export 單元測試。
- 保持 CPU/NumPy-first。

Definition of done：

- `py -m pytest` passes。
- CLI 可以從 synthetic data 產生 SVG 和 metrics。
- 沒有 GUI dependencies。

## Phase 1: Time Series MVP

目標：做出第一個對有限 time-series data 有用的 compressor。

支援輸入：

```text
CSV(time, value)
```

Methods：

- RDP simplified path。
- Fourier center function。
- Fixed display-resolution SVG sampling。
- 可重現 model 的 `demo.py` export。

Metrics：

- RMSE
- MAE
- max absolute error
- R2
- compression ratio by count
- generated file sizes

成功條件：

```text
1,000,000 samples
  -> compact visual model
  -> SVG opens in a browser
  -> demo.py reproduces the model
  -> metrics report compression ratio and error
```

## Phase 2: Center Function + Channel Model

目標：超越單一 reconstructed line。

概念：

```text
center(t) = fitted function
band(t) = fitted uncertainty / residual envelope
valid range = center(t) +/- k * band(t)
```

初始實作：

- `ChannelModel` 包裝 Fourier center function。
- residual calculation。
- `global_std` band。
- `rolling_std` band。
- band curve 的 RDP simplification。
- `rolling_quantile` band 延後。

SVG output：

- center path
- translucent channel
- optional outlier markers

Metrics：

- coverage ratio
- outlier count
- mean band width
- max band width
- center RMSE
- channel model size

這一階段很重要，因為它把 visual fidelity 表示成區間，而不是只有中心線。

## Phase 3: `.vizasset` Package Format

目標：定義 compressor、editor、RRKAL 之間的 handoff contract。

Package shape：

```text
example.vizasset/
  asset.json
  model.json or model.npz
  preview.svg
  metrics.json
  demo.py
```

`asset.json` 應包含：

- source summary
- model type
- method parameters
- model parameter file references
- metrics summary
- export profiles
- RRKAL lineage hints

Definition of done：

- Package manifest read/write round trip。
- CLI 可以 build `.vizasset`。
- Package 包含 compact model parameters、preview、metrics、demo。
- Editor 可以不用 raw data 也開啟 package。

目前狀態：

- Minimal package writer exists。
- `asset.json` includes file hashes and lineage notes。
- `model.npz` stores RDP, Fourier, optional channel compact parameters。
- Fourier/channel/residual readback can reconstruct renderable arrays。
- Irregular time-domain reconstruction supports preserved x values and compressed linear-plus-delta encoding。
- Package verification exists for manifest/files/hash/model-array/reconstruction self-consistency。

下一步：

- 原始輸入可用時，加入 source-backed fidelity verification。
- 輸出 review packets，記錄 accepted error budgets 與 baseline comparison。
- 加入 schema fixtures，讓後續 agent 驗證 backward compatibility。

## Phase 4: 2D Curve And Shape Compression

目標：支援 2D paths 與 closed contours 的 geometry-aware vectorization。

Topology classification：

- `open_curve`
- `closed_curve`
- `multi_contour`

Methods：

- open/closed curves 的 RDP。
- parametric Fourier：`x(t), y(t)`。
- radial Fourier：由 selected center 得到 `r(theta)`。
- 必要時加入 Bezier path fitting 來降低 SVG size。

Center selectors：

- centroid
- area centroid
- geometric median
- bounding-box center
- Chebyshev center, if practical

Metrics：

- Chamfer distance
- Hausdorff distance
- area error
- closedness error
- self-intersection warnings

Definition of done：

- Closed contour 可以被 radial Fourier 壓縮並輸出 SVG。
- 不同 center choices 可以 benchmark。

## Phase 5: Anchor And Focus Models

目標：用更好的 coordinate systems 降低 model complexity。

概念：

```text
single center -> radial distance
dual focus -> elliptic distance representation
multi-anchor -> distance field / skeleton-inspired representation
```

初始 dual-focus method：

- 用 PCA 找 long axis。
- 沿 long axis 放兩個 foci。
- 用 `d1 + d2`、`d1 - d2` 這類 distance features 編碼 boundary。
- 對 resulting functions fit Fourier 或 spline models。

Use cases：

- elongated objects
- ellipse-like objects
- two-ended contours

Definition of done：

- Strategy benchmark 可以在 synthetic elongated contours 上比較 radial center 與 dual-focus representation。

## Phase 6: Strategy Selector

目標：讓使用者指定 fidelity budget，而不是手動選 algorithm。

Input：

```text
target_error
target_format
priority = smallest | fastest | most_editable | most_compatible
```

Candidate methods：

- direct sampled SVG
- RDP
- Fourier center
- Fourier channel
- radial Fourier
- dual-focus model

Selection rule：

```text
choose the smallest model/export that satisfies the fidelity budget
```
