# 專案可行性、學術根基與商業變現匯報

本文件是給「主寫 / 主要開發者 / 專案決策者」看的匯報版。語氣刻意保持可辯護：強調已驗證成果，也標出仍需文獻引用或後續實證的部分。

相關引用整理見 [ACADEMIC_REFERENCES.zh-TW.md](ACADEMIC_REFERENCES.zh-TW.md)。

## 一、核心定位

RRKAL Visual Compressor 的定位不是一般圖表工具，也不是通用壓縮器。它是一個針對「具備視覺結構的大型資料」的函數化視覺資產編譯器。

傳統 SVG 會把點數直接變成輸出大小：

```text
N samples -> O(N) SVG path
```

本專案改成：

```text
N samples -> O(C + M + R) visual asset
```

其中：

- `C`：主函數模型，例如 Fourier coefficients、spline knots、future radial/implicit models。
- `M`：metadata，例如 domain、branch、topology、manifest、hash。
- `R`：residual compensation，例如 sparse outliers、noise layer、channel band。

核心 sweet spot 是：

```math
|C| + |M| + |R| < |B|
```

其中 `B` 是 baseline，例如 direct SVG、CSV.gz、JSON.gz，或其他傳統輸出格式。

更保守的專案表述是：

```text
A verified function-based compressor for visual-structured datasets.
```

中文：

```text
針對視覺結構資料的可驗證函數化壓縮器。
```

## 二、目前已完成的工程證據

目前主線已具備：

- time-series analyzer
- RDP compressor
- Fourier compressor
- Fourier channel model
- sparse residual layer
- Fourier residual noise layer
- irregular x-domain preserve/compressed/auto policies
- `.vizretain` / `.vizclean` / `.vizasset`
- package self-verification
- source-backed fidelity verification
- `review.json` review packet
- review acceptance gate：`--require-review-pass`
- direct SVG baseline evidence

最近本地測試：

```text
34 passed
```

## 三、100,000 點 smoke test 實測結果

測試命令：

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --svg-samples 1200 --channel --direct-svg --package --review-packet --review-max-rmse 0.003 --review-max-error 0.05 --out evaluation_smoke
```

實測摘要：

| 指標 | 結果 |
| --- | ---: |
| source samples | 100,000 |
| Fourier terms | 96 |
| Fourier count ratio | 1041.67x |
| Fourier RMSE | 0.0018466 |
| Fourier MAE | 0.0003929 |
| Fourier max error | 0.0403325 |
| Fourier R2 | 0.9999779 |
| Channel coverage, K=3 | 95.549% |
| `model.npz` | 9,005 bytes |
| whole package, including preview/review | 74,656 bytes |
| direct SVG baseline | 1,599,758 bytes |
| direct-SVG-to-package ratio | 21.43x |
| source numeric arrays / package ratio | 21.43x |

這個結果不能推廣到所有資料集，但足以證明：

```text
在 smooth structured time-series 上，函數化視覺資產有明確壓縮優勢。
```

## 四、數學正確性邊界

本專案不宣稱：

```text
任意資料都能被函數化壓縮。
```

本專案宣稱：

```text
若資料具有可被低複雜度函數捕捉的視覺結構，
則可以用 basis + residual 建立較小且可驗證的視覺資產。
```

核心模型：

```math
D(x) \approx F_\theta(x) + R(x)
```

驗證條件：

```math
\epsilon(D, decode(P)) \leq \tau
```

其中：

- `D` 是 source dataset。
- `P` 是 `.vizasset/.vizretain/.vizclean` package。
- `decode(P)` 是解碼後的 retained 或 center signal。
- `\tau` 是誤差預算。

這是 soundness by verification，不是 universal completeness。

## 五、學術根基對應

以下是合理的學術對應方向；目前引用整理在 `ACADEMIC_REFERENCES.zh-TW.md`：

| 本專案概念 | 學術/技術對應 |
| --- | --- |
| Fourier / spline basis | Functional Data Analysis, basis expansion |
| smoothing + residual | signal denoising, robust statistics |
| channel band | confidence/envelope modeling |
| sparse outlier layer | anomaly modeling / sparse residuals |
| radial distance function | shape descriptors |
| 2D closed contour Fourier | Fourier descriptors |
| LOD / multiresolution | wavelet / multiresolution analysis |
| implicit/SDF future path | signed distance fields, implicit surfaces |

注意：這些是對應方向，不等於本 repo 已經完成相關完整實作。

## 六、技術前沿對齊，但避免過度宣稱

可以說：

```text
本專案與現代圖形學、幾何處理、神經場、SDF、LOD 等方向共享「用連續表示取代純離散點列」的思想。
```

不建議直接說：

```text
本專案已處於 SOTA 浪尖。
本專案顛覆計算機圖形學。
Nanite 底層核心大量依賴 SDF。
```

原因是這些句子需要更嚴格的官方或論文引用。對主寫匯報時，可以把它們改成：

```text
這條路線與多個前沿方向相容，但目前仍以 time-series visual compression MVP 為主。
```

## 七、商業化假設

目前比較可信的三條商業路徑：

### 1. FinTech / 高頻圖表

痛點：

- 高頻 tick data 大。
- browser/client 畫大量點會卡。
- 前端需要快速縮放與重建。

價值主張：

```text
server-side compile -> small visual asset -> client-side reconstruction
```

可賣形式：

- visualization SDK
- chart asset compiler
- hosted conversion API

### 2. IIoT / 邊緣感測

痛點：

- 高頻感測資料多。
- 傳輸頻寬昂貴。
- 設備端需要先摘要或壓縮。

價值主張：

```text
edge device computes compact visual/diagnostic asset
```

可賣形式：

- edge compressor license
- per-device annual license
- industrial monitoring plugin

### 3. GIS / Digital Twin / BIM

痛點：

- 邊界、地形、管線、軌跡、感測資料都可能很大。
- renderer/editor 不一定需要 raw data，只需要可重建的 visual asset。

價值主張：

```text
large geometry/time-series source -> compact package -> editor/renderer stream
```

可賣形式：

- CAD/GIS export plugin
- digital twin asset compiler
- renderer bridge package format

## 八、下一步建議

### 近期：強化可驗證性

- review packet schema fixture
- review packet verifier
- baseline suite：direct SVG、CSV.gz、JSON.gz、Parquet
- benchmark report export

### 中期：2D 曲線壓縮

- open curve / closed curve classifier
- parametric Fourier：`x(t), y(t)`
- radial Fourier：`r(theta)`
- area error、Hausdorff distance、Chamfer distance

### 長期：SDF / implicit / 3D

- 先做 2D SDF，不直接跳 3D。
- 加入 branch/domain/topology constraints。
- 建立 mesh reconstruction 與 topology fidelity metrics。

## 九、對主寫的簡短結論

這個專案目前不是空想。它已經具備：

- 可執行 CLI
- package format
- verification
- review packet
- direct SVG baseline evidence
- 34 項本地測試
- 100,000 點 smoke test 實測壓縮優勢

但它也不是 universal compression。最合理的定位是：

```text
針對視覺結構資料的可驗證函數化壓縮框架。
```

建議繼續投入，但要用 benchmark 和 review packet 控制每一次技術主張，避免把研究假說包裝成已證明定理。
