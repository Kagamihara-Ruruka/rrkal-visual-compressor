# 研究筆記：RRKAL Visual Compressor 的可辯護壓縮方向

日期：2026-05-28  
專案：`rrkal-visual-compressor`

## 1) 研究範圍與定位

本專案目前關注的是**可辯護性**，而不是「萬用壓縮理論」。
所有主張都必須是條件式、可重現、可量測的。

每次比較都要先明確：

- 相同輸入樣本域與評估長度，
- 固定目標下的重建指標（`R2`、`RMSE`、`Max-AE`），
- 明確的複雜度與 payload 指標（係數數、殘差筆數、metadata 位元組）。
- 在報告中分開列出精度益處與壓縮益處。

## 2) 核心風險與檢查

### A. 全域模型的局部擴散
全域 Fourier 容易把局部突變往遠端「汙染」。

- 使用 `locality_leakage_metric` 量測。
- 用 step 類合成訊號當壓力測試。

### B. 不規則時間軸假設
時間戳若不規則，重建容易產生時間漂移。

- `domains.py` 明確保存 x-domain 策略（`stored_x`、`linear_plus_rdp_delta`、`linspace_from_min_max`），
- `packages.py` 驗證 `x_delta_t`、`x_delta_values` 等元資料欄位。

### C. 通道耦合
多通道資料並非彼此獨立。

- `compress_multichannel_fourier_pca` 先做 PCA/SVD 共享潛在軸，再做 Fourier。

### D. 殘差層過重
若殘差層過大，整體壓縮效果會失效。

- 所有比較列都同步記錄殘差佔比與 payload。

## 3) 已實作基線

`src/vizcompress/research.py` 已包含：

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold`
- `locality_leakage_metric`
- `compress_fourier_with_linear_detrend`
- `adaptive_residual_threshold`
- `compress_fourier_with_rdp_budget`
- 前面件配套的 frontier 掃描邏輯（於 sweep 腳本）

`tests/test_research.py` 已覆蓋：

- step / spikes 的局部洩漏比較，
- 有限值與形狀一致性，
- 不規則時間軸穩定性，
- 多通道 PCA，
- Haar 與自適應殘差行為，
- RDP 預簡化的約束與單調性。

`tests/test_research_sweep.py` 已覆蓋：

- frontier CLI ratio 解析，
- 無效 ratio 拒絕，
- RDP frontier 保留點數單調性，
- 在 `r2_gate` 下的最佳點選擇。

## 4) 視覺化前的簡化（取樣預算）

你的想法正確：簡化不是另一種壓縮理論，而是**放在擬合前的取樣預算控制**。

- 根據輸出影像尺寸 `W×H`，可見資訊有自然的上限。
- 過量點數通常不會提升可視結果。
- 在 Fourier / polynomial / wavelet 前先做簡化，可降低渲染前處理與擬合成本。

### 4.1) RDP 預簡化基線

- 輸入 `target_keep_ratio`
- 內部以二分搜 `epsilon` 讓保留點數接近目標
- 對簡化結果做 Fourier 擬合
- 插值回原始 x-域

實驗上，RDP 可降低運算端點數，但若保留點仍多，payload 可能反而上升，因此目前作為獨立控制參數，而非預設主路徑。

## 5) Frontier 掃描（新檢測機制）

`scripts/run_defensible_research_sweep.py` 新增：

- `--run-rdp-frontier`
- `--rdp-frontier-ratios`
- `--rdp-frontier-min-keep`
- `--rdp-frontier-max-keep`

frontier 輸出會記錄每個 ratio 的：

- 實際保留比例與保留點數
- R2、RMSE、payload ratio
- 每個候選點的 `r2_gate_pass` 與 `gate_reason`
- 在 `r2_gate` 下的最佳點

這樣可以直接找出每種資料型態的「甜蜜區」而非拍腦袋挑一個固定比率。

## 6) Payload 估算（保守）

目前使用保守估算，不做 entropy coding：

- `raw_payload_bytes = sample_count * 2 * 8`
- `payload_fourier ≈ parameter_count * 24 + 8`
- `payload_piecewise_fourier = Σ(24 * segment_param_count) + len(breakpoints) * 8`
- `payload_piecewise_polynomial = approx_param_count * 8 + 2 * segment_count * 8 + len(breakpoints) * 8`
- `payload_rdp ≈ kept_points * (2*8 + 8) + payload_fourier`

輸出中都有 `payload_ratio = raw_payload_bytes / payload_bytes` 便於對齊比較。

## 7) 這樣跑

```bash
py -m pytest tests/test_research.py tests/test_research_sweep.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32 --include-piecewise-polynomial --run-rdp-frontier --rdp-frontier-ratios 0.02,0.05,0.10,0.20,0.30
```

## 8) 判讀原則

- 若 `R2` 上升但 payload 也同步上升，不能直接算勝出，要看壓縮比是否真的更好。
- 局部表現變好但主體精度大幅下降，請直接拒絕。
- 在固定條件下，同時看見精度與 payload 的穩定進步，才可進入下一個執行檢核點。
