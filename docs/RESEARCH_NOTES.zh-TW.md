# 研究筆記：可證明的壓縮方向（RRKAL Visual Compressor）

日期：2026-05-27
專案：`rrkal-visual-compressor`

## 1) 測試重點

本專案的目標是讓壓縮路徑「可被檢驗」，而非宣稱一個普適定理。
只保留在可度量條件下成立的方法。

- 同一組輸入、同一個取樣點數；
- 使用一致的重建度量（R2 / RMSE / Max-AE）；
- 同步報告複雜度與位元組開銷（參數數、殘差比例、metadata）。

## 2) 風險模型（硬條件）

### 風險 A：全域 Fourier 的局部擴散
Fourier 是全域基底，局部突變可能在全域擾動（Gibbs）。

- 我們用 `src/vizcompress/research.py` 的 `locality_leakage_metric` 作為守門閘；
- 步階訊號是壓力測試。

### 風險 B：非均勻 x 軸
- 非均勻時間軸若未明確處理，會造成重建偏差。
- `domains.py` 的 `stored_x` / `linear_plus_rdp_delta` / `linspace_from_min_max` 已列為不同策略。
- `packages.py` 的 x 軸壓縮 metadata 校驗已修正。

### 風險 C：多通道耦合
- 單通道獨立壓縮會浪費跨通道共用結構。
- `compress_multichannel_fourier_pca` 在 PCA/SVD 降維後再做 Fourier，作為第一條替代。

### 風險 D：殘差層體積反彈
- 殘差層可能吃掉大部分收益。
- 目前回報每個方法的 `payload_ratio`，以及殘差層可估計 payload，避免只看誤差。

## 3) 已落地的研究 baseline

`src/vizcompress/research.py` 目前包含：

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold`（Haar + 閾值）
- `compress_fourier_with_linear_detrend`
- `adaptive_residual_threshold`
- `locality_leakage_metric`
- `compress_fourier_with_rdp_budget`（RDP 預簡化 + Fourier）

`tests/test_research.py` 對應覆蓋：

- 跳變點偵測與區域外洩比較
- 分段 Fourier/多項式可行性
- 非均勻取樣
- 多通道 PCA 對比
- Haar 門檻 baseline
- 線性去趨勢
- 自適應殘差門檻

## 4) 點化簡與渲染預算

你的「先做 polyline simplification」是有意義的：

- 目標畫布 `W×H` 下可視化像素可見度上限約 `2P`（P 為可視度量）；
- 在這個預算上再做函數近似（Fourier / polynomial / wavelet），可減少無效點與後續 payload。

可測量：

- 誤差-降採樣單調性；
- 壓縮成本（payload）變化；
- 在不同 scale 的穩定性。

### 4.1) RDP 預算 baseline 的觀察

已新增 `compress_fourier_with_rdp_budget`：

- 用 `target_keep_ratio` 表示可見化可用點預算；
- 二分搜出對應的 RDP `epsilon`；
- 在簡化後點列做 Fourier 擬合；
- 再插值回原始 x 軸回推重建。

目前實驗（`--locality-mode any`、`--terms 16,32,64`）顯示：

- 先簡化可減少渲染前處理點數；
- 但若保留點過多，`payload` 可能不降（因為同時要存 RDP 控制點與 Fourier 參數）；
- 因此先當作「可調旋鈕」，避免直接取代主 baseline。

報表估算式：

$$
\text{payload}_{rdp}\approx K(2f+8)+(24C+8)
$$

- $K$：RDP 保留點數；
- $f$：float64 位元組數（8）；
- $C$：簡化後 Fourier 係數個數。

## 5) 為何這裡是「可被證明」而非「萬能公式」

我們只聲明：

1. 信號族先決定（平滑、週期、分段規則、有限雜訊）；
2. 相同資料、相同評估域；
3. 相同誤差條件下比較。

同時追求：

- 證據先行（defensible checkpoint）；
- 可重現（隨機種子固定）；
- 準確記錄 x 軸策略。

### 當前 checkpoint 狀態

- strict（`--locality-mode strict`，預設）：`--terms 16,32,64 --r2-gate 0.99 --leakage-gate 0.25 --max-adaptive-keep-ratio 0.45` 得到 `0 / 16` 通過。
- any（`--locality-mode any --r2-gate 0.98 --leakage-gate 0.85 --max-adaptive-keep-ratio 0.45`）得到 `12 / 16` 通過。

解讀：strict 是硬門檻；any 用來定位可改進路徑。

## 6) 報告欄位（含 payload）

- `raw_payload_bytes = sample_count * 2 * 8`
- Fourier payload（估算）`= coeff_count * 24 + 8`
- piecewise payload（估算）`= Σ segment_bytes + breakpoints*8`
- polynomial payload（估算）`= (approx_parameter_count + 2*segment_count + breakpoints) * 8`
- rdp_prefilter payload（估算）`= K(2f+8)+(24C+8)`（`f=8`）

這些只是估算，不含壓縮器額外封裝（entropy coding / container overhead）。

## 7) 執行檢查清單

```bash
python -m pytest tests/test_research.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32,64 --out-json docs/benchmarks/defensible_hardening_report.json --out-md docs/benchmarks/defensible_hardening_report.md
```

## 8) 結果判讀

- R2 若上升但 payload 也同步惡化，不能算有效贏家。
- 局部外洩降低但在 spikes/steps 上誤差失控，不能上線。
- 在同一條件下，若 fidelity 與 payload 同時改善，才可提昇到下一級。
