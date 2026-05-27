# 影片式函數化壓縮原型

## 1. 核心假設

對影像序列而言，

$$
V = \{I_t\}_{t=1}^{T},\quad I_t\in\mathbb{R}^{H\times W}
$$

我們用「低秩空間基底」與「時間傅立葉係數」描述：

$$
I_t(x,y)\approx \bar I(x,y)+\sum_{k=1}^{r} c_k(t)\,\phi_k(x,y),
$$

其中

$$
c_k(t)\approx \sum_{m=1}^{M} a_{k,m}\exp\left(j\omega_m t\right).
$$

模型儲存：

- `mean_frame`：空間平均影像 $\bar I$
- `spatial_modes`：空間基底 $\phi_k$
- `temporal_models`：每一個基底的傅立葉時間係數

解碼後直接在請求的輸出影格數或 FPS 下取樣重建，避免先輸出整包原始像素。

## 2. 為什麼符合「渲染函數化」方向

對下游渲染器可定義：

$$
O = \mathrm{render}(E,\;N,\;P,\;B),
$$

其中

- $E$：編碼模型（不是原始像素）
- $N$：輸出影格數 / 目標 FPS
- $P$：視域（viewport）或 LOD 策略
- $B$：預算（誤差、記憶體、時間）

這讓前端只解出「有意義」那一部分幀資料。

## 3. 目前原型

原型入口：`src/vizcompress/video.py`。

目前已實作：

- `VideoCube`：可重現的影像序列輸入模型
- `compress_video`：空間降秩 + 每模態時間傅立葉
- `reconstruct_video_at_samples`：輸出幀數無關的重建
- `estimate_video_model_ratio`：提供大小與重建誤差的一次性報告
- `src/vizcompress/video_benchmarks.py`：幀數 / rank / 時間項數掃描
- `vizcompress video-bench` CLI：可重複跑基準測試

## 4. 可追蹤證據

基準輸出同時提供：

- 壓縮倍率
- RMSE、MAE、最大誤差
- $R^2$
- model bytes 與 raw bytes
- row summary（最佳列、最佳壓縮倍率列）

這些是可機器驗證的量化結果，不是口頭概念。

## 5. 邊界聲明

- 不主張此法普遍優於所有影片格式。
- 尚未完成 `.vizasset` 的 3D 通用資產規格整合。
- 不取代既有 raster/mesh 管線，而是提供可替代分支。

## 6. 下一步執行

1. 固定可重複的合成資料集規格（含雜訊、步階、漸變與稀疏干擾）。
2. 加上 CLI output schema 契約測試（JSON schema/checksum）。
3. 建立一個可對照的 2D 幾何流程（後續階段）並與影片流程共用一份策略選擇介面。
4. 將外部參考基線（如影格壓縮）接到 `video-bench` 報告中（未來階段）。

## 7. 命令示例

```powershell
py -m vizcompress.cli video-bench --frame-counts 120,240 --height 32 --width 32 --rank-values 2,4 --temporal-terms-values 8,16 --out benchmark_outputs/video.json --report-md benchmark_outputs/video.md
```

