# 影像函數化壓縮原型

## 核心假設

一段影片可寫成：

$$
V=\{I_t\}_{t=1}^{T},\quad I_t\in\mathbb{R}^{H\times W}
$$

我們把它看成時間與空間分離的函數形式：

$$
V(t,x,y)\approx\sum_{k=1}^{r}c_k(t)\,\phi_k(x,y)+\bar{I}(x,y)
$$

其中：

- $\phi_k$ 是空間基底（SVD/POD 模式），
- $c_k(t)$ 是時間軌跡，
- $\bar{I}$ 是時間平均影像。

每一條時間軌跡再用 Fourier 係數建模，得到兩層流程：

1. 先一次性編碼空間基底，
2. 再編碼每條模式的時間係數，
3. 輸出時只解碼當前幀率/視區需要的幀。

## 和「渲染是函數」的關係

這是你要的實作化版本：

$$
O=\mathrm{render}(E,v,b,s)
$$

- $E$：編碼資產（空間基底 + Fourier 參數），
- $v$：viewport / LOD 策略，
- $b$：預算（幀數、可容許誤差），
- $s$：風格/材質策略。

它不必先還原成完整逐點張量再上屏繪，而是直接產生當前需要的畫面數值。

## 要先做的可驗證檢核

- 時間重建誤差（像素空間）：
  - RMSE、MAE、max-abs
- 參數體積：
  - 平均影格 + 空間基底 + Fourier 參數大小
- Break-even：
  - `size_ratio = raw_bytes / model_bytes`
- 吞吐：
  - 目標 FPS 下重建耗時

只在以下成立時才應該宣稱可行：

$$
|C_{video}| + |M_{meta}| < |B_{baseline}|
$$

## 本專案的驗證起手式

原型目前已準備：

- `VideoCube`：影片輸入結構，
- `compress_video`：空間低秩 + 時間傅立葉壓縮，
- `reconstruct_video_at_samples`：指定輸出幀數重建，
- `estimate_video_model_ratio`：尺寸與誤差證據。

## 風險備註

- 常數影像或極端雜訊影像不一定可被壓縮得更好。
- 直接對巨大影片做 SVD 成本高，實務上要加：
  - 降解析度預處理、
  - 隨機化 SVD、
  - 區塊式增量更新。
- 這是「渲染函數化」的研究路線，不是萬能壓縮結論。
