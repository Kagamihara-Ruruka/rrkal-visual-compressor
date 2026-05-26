# 概念模型

這個專案不是要證明 universal compression。它要做的是：針對有視覺結構的資料，建立可驗證的函數化壓縮器。

核心主張刻意縮小：

```text
某些大型視覺資料具有低複雜度結構。
如果我們明確建模這個結構，就有機會比逐點輸出的 SVG 更小，
同時仍滿足可量測的誤差預算。
```

## 可表示不等於可壓縮

任何有限資料集都能被某個函數表示。對樣本：

```math
D = \{(x_i, y_i)\}_{i=1}^{N}
```

總是可以找到某個插值函數 `f`，使得：

```math
f(x_i) = y_i
```

對每個 sample 都成立。但這不代表有壓縮價值。如果函數需要太多係數、太高精度，或殘差層太大，它可能跟原始資料一樣大，甚至更大。

真正有用的檢查是：

```math
|C| + |M| + |R| < |B|
```

其中：

- `C` 是 compact function model。
- `M` 是 metadata，例如 domain、branch、topology、package manifest。
- `R` 是為了滿足誤差預算而保留的 residual data。
- `B` 是 baseline export，例如 direct SVG、CSV.gz、JSON.gz 或其他參考格式。

如果這個不等式不成立，compressor 就應該回報這個模型對該資料沒有優勢。

## Basis Plus Residual

實務模型是：

```math
D(x) \approx F_\theta(x) + R(x)
```

其中：

- `F_\theta` 是低複雜度 basis model，例如 Fourier、spline、radial distance，或其他 fitted function。
- `R` 存 basis model 無法便宜解釋的部分。

白話就是：

```text
original data = main shape + residual details
```

主形狀用函數壓縮。細節依情況存成 sparse points、secondary Fourier layer、statistical noise summary，或在 clean profile 允許時丟棄。

## 可驗證逼近

這個專案不能要求使用者憑感覺相信模型。每個被接受的壓縮結果都必須能 decode，並且能量測。

對原始資料 `D` 與解碼重建 `\hat{D}`：

```math
\epsilon(D, \hat{D}) \leq \tau
```

其中：

- `\epsilon` 是選定的 error metric。
- `\tau` 是使用者或 profile 設定的 error budget。

時間序列 MVP 先使用：

```math
RMSE = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(y_i - \hat{y}_i)^2}
```

```math
MAE = \frac{1}{N}\sum_{i=1}^{N}|y_i - \hat{y}_i|
```

```math
MaxError = \max_i |y_i - \hat{y}_i|
```

這些 metric 不證明「最佳壓縮」。它們證明的是：這次產出的 package 是否滿足宣稱的 fidelity 條件。

## 分支與 Domain 約束

隱函數有一個特殊風險：一個方程可能有多個合法解分支。

例如：

```math
y^2 = x
```

有兩個分支：

```math
y = \sqrt{x}
```

以及：

```math
y = -\sqrt{x}
```

如果 visual asset 只存方程式，decoder 可能選到數學上正確、但不是原始形狀的分支。因此未來 implicit package 不能只存 function：

```text
function + domain + branch selector + anchors + topology + residual
```

目前 time-series MVP 也有類似問題，表現在 x-domain：

- uniform domain 可以用 `x_min`、`x_max`、sample count 重建。
- irregular domain 必須完整保存，或用明確 error budget 壓縮。

## 健全性邊界

本專案追求的是 soundness by verification：

```text
如果 package 說自己有效，它就必須能被 decode，
並通過 manifest、hash、model arrays、reconstruction constraints 的檢查。
```

本專案不追求 universal completeness：

```text
compressor 不承諾每個資料集都能被壓成更小的 function asset。
```

這是工程系統比較正確的邊界。成功的 package 可以被信任；不適合的資料則 fallback 到 direct 或保守格式。

## 目前的 Package Verification

`vizcompress verify` 分成兩個層級。

### Package 自洽性

沒有 source dataset 時，`vizcompress verify package.vizretain` 檢查 package 的自洽性：

- manifest schema 與必要欄位
- 必要檔案
- file byte sizes
- SHA-256 hashes
- `model.npz` 必要 arrays
- x-domain array consistency
- residual layer array consistency
- Fourier 與 retained-signal reconstruction 是否為 finite values

這證明 package handoff 內部是 sound 的。但它還不證明 decoded signal 逼近原始 raw source，因為 package 目前不嵌入 raw input。

### Source-Backed Fidelity

如果原始 source 還在，verifier 可以 decode package，直接跟 source 比較：

```powershell
py -m vizcompress.cli verify outputs/model.vizretain --synthetic 100000 --max-rmse 0.01
```

或：

```powershell
py -m vizcompress.cli verify outputs/model.vizretain --csv data.csv --x-column time --y-column value --max-rmse 0.01
```

數學上檢查的是：

```math
\epsilon(D, decode(P)) \leq \tau
```

其中：

- `D` 是 source dataset。
- `P` 是 package。
- `decode(P)` 是選定的 decoded signal，通常是 retained signal。
- `\tau` 是要求的 error budget。

這是本專案 soundness claim 的第一個可執行形式。它仍然不證明 package 是最小可能表示；它只證明這個 package 在指定 metric budget 下，decode 後足夠接近這個 source。

完整 production verification 之後還需要：

- 能讀到原始輸入資料，或
- build time 產生 review packet，記錄 source fingerprint 與已接受的 error metrics。

## Review Packets

Review packet 是 package 被接受的持久證據。它不是 raw data，而是這次檢查的摘要：

```text
review.json
  source fingerprint
  verification policy
  package self-consistency result
  source-fidelity result
  accepted = true | false
```

Source fingerprint 會儲存 numeric x/y arrays 的 hash：

```math
h_x = SHA256(bytes(x))
```

```math
h_y = SHA256(bytes(y))
```

這讓後續 agent 可以檢查：現在拿到的 source 是否就是當時產生 accepted metrics 的 source。

使用 `--require-review-pass` 時，build command 會把 `accepted: false` 視為硬失敗。這就是「不要接受超出宣稱 error budget 的 compressed asset」在操作層的形式。
