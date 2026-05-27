# 研究檢核點 v1.1：可辯護壓縮路線

日期：2026-05-28  
負責：RRKAL Visual Compressor  
範圍：時間序列 / 2D 預覽層（尚未進入完整 3D 管線）

## 1) 目前測試中的核心命題

本專案不嘗試證明「萬用數學定理」。  
我們正在驗證的是：

> 對於有明確結構的資料（平穩趨勢 + 區域細節 + 適度雜訊），
> 「可壓縮的函數表示」加上「受控殘差層」，在可量測條件下可優於原始逐點輸入。

這是**可執行的工程命題**，非萬用真理聲明。

## 2) 當前風險假設（已轉成檢測項）

1. **全域 Fourier 的局部漏洩**  
   尖變點可能產生非局部波紋。  
   ✅ 已用 `locality_leakage_metric` 量測。

2. **不規則時間軸處理**  
   時間戳不規則時必須明確編解碼策略。  
   ✅ `domains.py` 已有多種 `x` 編碼路徑並保留驗證。

3. **多通道耦合**  
   通道通常不是彼此獨立。  
   ✅ 已加入 PCA/SVD 的多通道 baseline。

4. **殘差預算失控**  
   第二層 correction 可能吃掉壓縮效果。  
   ✅ 已追蹤殘差比例與 payload。

5. **畫面像素預算驅動取樣**  
   超過顯示解析度的點數是浪費。  
   ✅ 已加入 RDP 預簡化路徑，並新增 frontier 掃描。

## 3) 本檢核點門檻規則

在 `scripts/run_defensible_research_sweep.py` 每一列結果中要求：

- `R2 >= r2_gate`（預設 `0.99`）
- 局部方法是否過門檻：
  - `strict`（預設）：piecewise Fourier 與 detrended Fourier 都要過
  - `any`：兩者任一通過即可
- 可選：`--include-piecewise-polynomial` 開啟 piecewise polynomial 候選
- `adaptive_keep_ratio <= max_adaptive_keep_ratio`（預設 `0.45`）

同時符合者標記為 `defensible = true`。

## 4) RDP frontier 掃描（新）

指令範例：

```bash
py scripts/run_defensible_research_sweep.py \
  --terms 16,32 \
  --include-piecewise-polynomial \
  --run-rdp-frontier \
  --rdp-frontier-ratios 0.02,0.05,0.10,0.20,0.30 \
  --out-json docs/benchmarks/defensible_hardening_report_frontier.json \
  --out-md docs/benchmarks/defensible_hardening_report_frontier.md
```

輸出會包含：

- 每個資料集/項數的 `target_keep_ratio` 掃描點
- 每點的實際保留比例、R2、payload ratio、實際保留點數
- 在 `r2_gate` 下的最佳甜蜜點
- 單調性檢查（`target ratio` 越大時實際保留比例不應變小）

## 5) 前進與回退條件

可前進條件：

- JSON + MD 能重複產出且一致
- 固定資料集 `steps / spikes / irregular / multiscale / smooth` 至少有一筆
  非平凡通過（`defensible`） 
- frontier 掃描主要指標穩定（同一命令多次結果一致）
- `tests/test_research_sweep.py` 通過，代表 frontier ratio 解析、單調性、
  最佳點選擇有單元測試守住
- noise frontier 在固定 seed 下可重現，並能記錄高 sigma 時是否發生
  `r2_below_gate`
- frontier 候選點必須同時通過 fidelity（`r2_gate`）與儲存效益
  （`frontier_min_payload_ratio`）門檻

連續兩個 checkpoint 持續發生硬失敗或結果漂移時，需回退與重設參數。

## 6) 下一步

- 逐步提升 gate 嚴格度
- 加入低、中、高噪音層級的固定測試區
- 比較 `smooth`、`spikes`、`multiscale` 三種資料族群下的 noise frontier 結果
- 加入「解碼與渲染時間」作為第二報表軸（目前優先做 payload 與 fidelity）
