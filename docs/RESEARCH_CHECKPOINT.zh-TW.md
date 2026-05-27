# 研究里程碑 v1：可驗證視覺編碼器（Defensible Visual Codec）

日期：2026-05-27  
主專案：RRKAL Visual Compressor  
範圍：時間序列與 2D 曲線預覽層（不含完整 3D 流程）

## 1) 核心研究命題

目前只測試一個命題：

> 大型且有結構的視覺訊號，在可測量的條件下，可由「壓縮模型」`F` +
> 可界定殘差層 `R` 組合，讓互動與傳輸成本低於逐點訊息。

這是「可證明一致性」方向，不是「普遍可行」方向。

## 2) 當前假設

1. 單一全域 Fourier 對突變資料不穩定。  
2. 分段局部基底（piecewise Fourier、局部多項式、Haar）可降低局部洩漏。  
3. 不規則時間軸必須有明確 x-domain 編碼策略，否則會產生偏移。  
4. 多通道壓縮需共享潛在結構（例如 PCA baseline）。  
5. 自適應殘差閾值可控制高雜訊下殘差膨脹。

## 3) 本里程碑門檻

對 `scripts/run_defensible_research_sweep.py` 的每一列結果：

- `R2 >= r2_gate`（預設 `0.99`）  
- 三種局部方案漏度皆小於等於 `leakage_gate`（預設 `0.25`）  
- `adaptive_keep_ratio <= max_adaptive_keep_ratio`（預設 `0.45`）

三項同時成立者標為 **defensible = true**。

## 4) 必做實驗集

固定項目（同參數重複執行）：

- `steps`
- `spikes`
- `irregular`
- `multiscale`
- `smooth`

Terms 固定：

- `--terms 16,32,64`

在 `steps / spikes / irregular` 這三種情境至少要各有一筆非平凡 `defensible` 通過前進下一階段。

## 5) 停止 / 進階判定

通過條件：

- 能產生可重現的 JSON/MD 報表  
- 在 `steps`、`spikes`、`irregular` 至少各有一筆通過  
- 在相同輸入下，`defensible_rows / rows_with_gate_fields` 在連續兩次 run 中穩定

若連續兩次檢核失敗，視為回退到上一方法或加強研究。

## 6) 下一步接力

里程碑通過後，啟動：

- 收斂門檻值；
- 加入像素導向（DPI）抽樣的視窗實驗；
- 加入「解碼時間」與「噪聲條件下 payload 成長」檢測。

研究順序維持：

1. **可測量的正確性**  
2. **可證明的 payload 管控**  
3. **視口感知執行效能**

