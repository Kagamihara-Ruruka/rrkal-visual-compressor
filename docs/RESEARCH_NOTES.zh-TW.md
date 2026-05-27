# 研究紀錄：RRKAL 視覺壓縮器的可驗證方向

更新日期：2026-05-27  
專案：`rrkal-visual-compressor`

## 1. 研究範圍與判讀邏輯

這個專案目前聚焦在「可防禦的壓縮流程」，不是在證明一個新的萬用數學公式。  
任何方法都需要同時滿足：

- 相同輸入、相同取樣長度比較；
- 相同誤差目標下比較（R²、RMSE、Max-AE）；
- 同步報告壓縮負載（係數數、保留殘差比例、元資料規模）；
- 忠實度與壓縮率分開報告，不互相掩蓋。

## 2. 四大風險（硬性限制）

### 風險 A：全域基底的局部污染
全域傅立葉在局部突變時，會把訊號能量擴散到非局部位置（吉布斯現象）。

- 使用 `src/vizcompress/research.py` 的 `locality_leakage_metric` 做警戒指標；
- 以階梯型訊號做壓測。

目前結論：在目前測試資料上，局部基線（piecewise）對斷點附近失真擴散較少，但不能直接推廣到所有資料。

### 風險 B：非均勻 x 軸
非均勻時間戳若處理不好，會破壞精度。

- 生產流程在 `domains.py` 已有 `stored_x`、`linear_plus_rdp_delta`、`linspace_from_min_max` 三條路徑；
- `packages.py` 已修正驗證鍵位，改為 `x_delta_t` / `x_delta_values`。

### 風險 C：通道耦合
逐通道壓縮忽略通道關係。

- `compress_multichannel_fourier_pca` 先做 PCA/SVD 降到共用 latent，再各 latent 做傅立葉，驗證多通道關聯。

### 風險 D：殘差負載反撲
殘差層若失控會吃掉壓縮收益。

- 目前已追蹤殘差負載，在波基準測試中輸出 `residual_payload_ratio`。

## 3. 已實作研究 baseline

`src/vizcompress/research.py`：

- `compress_fourier_piecewise`
- `compress_piecewise_polynomial`
- `compress_fourier_with_uniform_param`
- `compress_multichannel_fourier_pca`
- `compress_haar_threshold`（Haar + hard threshold）
- `locality_leakage_metric`

`tests/test_research.py`：

- 斷點資料漏泄比較
- piecewise/poly 局部可行性測試
- 非均勻 x 軸對齊測試
- 多通道 PCA baseline
- Haar threshold baseline

## 4. 新洞見：折線簡化是「螢幕解析度限制」的實作化

你提的折線簡化是穩固且實用的概念，不是另一條理論路徑，而是渲染前的取樣策略：

- 若螢幕可呈現寬度約 `P` 像素，不需要輸出明顯高於 `~2P` 的曲線採樣；
- 在簡化階段用 RDP、角度/曲率門檻、適應式節點刪除，先壓掉不可見細節；
- 再讓函數化（傅立葉、局部多項式、波）去擬合「已精簡」訊號。

這是穩健的工程順序：
1. 先決定視覺目標（解析度、dpi、允許誤差）；
2. 在誤差 ε 下做折線簡化；
3. 對簡化結果做函數壓縮。

這個方向可直接驗證：
- 在不同 ε 下誤差與取樣點數的單調性；
- 不同畫面大小的穩定壓縮行為；
- 殘差/保留係數是否同步下降。

## 5. 檢驗口令

```bash
python -m pytest tests/test_research.py -q
py scripts/run_defensible_research_sweep.py --terms 16,32,64 --out-json docs/benchmarks/defensible_hardening_report.json --out-md docs/benchmarks/defensible_hardening_report.md
```

## 6. 判讀規則

- R² 變好但負載也變差，不能當成勝利。
- 局部保真變好但尖峰/台階變差，不可進生產。
- 若同一個 ε/terms 下同時提升忠實度與降低負載，才算有資格進下一階段。

