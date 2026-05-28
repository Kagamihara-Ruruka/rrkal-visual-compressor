# 研究檢查點 v1.1：可辯護的壓縮路線圖

日期：2026-05-28  
負責專案：RRKAL Visual Compressor  
範圍：時間序列 / 2D 預覽層，尚未進入 3D 引擎層

## 1) 目前正在測試的核心主張

我們不是在證明一條放諸四海皆準的定理。  
目前假說是：

> 對於有明確結構的資料，例如平滑趨勢、局部細節與中等噪聲，緊湊的函數表示加上受控殘差層，有機會在可量測條件下優於原始點取樣。

這是一個**可測試的工程主張**，不是物理定律。

## 2) 目前的風險假說

1. **全域傅立葉的局部污染**
   尖銳跳變可能造成非局部的波紋假影。  
   目前用 `locality_leakage_metric` 量測。

2. **不規則 `x` 軸處理**
   不規則時間戳需要明確的 encode/decode domain 策略。  
   目前已有 `domains.py` 的 domain policy 與 payload 路徑檢查。

3. **多通道耦合**
   真實系統中的通道通常不是彼此獨立。  
   目前已加入 PCA/SVD 多軸 baseline。

4. **殘差層膨脹**
   第二層 correction 可能吃掉壓縮收益。  
   目前已追蹤 residual ratio 與 payload estimate。

5. **視角 / DPI 感知取樣預算**
   超過顯示解析度的過度取樣會造成浪費。  
   目前已加入 RDP pre-filter 路徑與 frontier sweep。

## 3) 本檢查點的 gate 政策

`scripts/run_defensible_research_sweep.py` 的每一列都檢查：

- `R2 >= r2_gate`，預設 `0.99`
- locality candidates 依照模式通過：
  - `strict`：piecewise Fourier 與 detrended Fourier 都要通過
  - `any`：任一方法通過即可
- 可選 `--include-piecewise-polynomial` 納入 piecewise polynomial candidate
- `adaptive_keep_ratio <= max_adaptive_keep_ratio`，預設 `0.45`

同時通過以上條件的列，才標記為 `defensible = true`。

## 4) RDP frontier 掃描

執行命令：

```bash
py scripts/run_defensible_research_sweep.py \
  --terms 16,32 \
  --include-piecewise-polynomial \
  --run-rdp-frontier \
  --rdp-frontier-ratios 0.02,0.05,0.10,0.20,0.30 \
  --out-json docs/benchmarks/defensible_hardening_report_frontier.json \
  --out-md docs/benchmarks/defensible_hardening_report_frontier.md
```

這會輸出：

- 每個 dataset / terms / target keep ratio 的掃描列
- 每個掃描點的實際保留比例與 payload ratio
- 依照 `r2_gate` 找出的最佳候選點
- 最佳候選點的 frontier tier：
  `strict_pass`、`exploratory_pass`、`demo_pass`、`reject`、`payload_reject`
- monotonic sanity flag：`actual_keep_ratio` 應隨 target ratio 非遞減
- JSON summary 與 Markdown 報表中的 tier histogram
- 可選 `--run-frontier-tier-matrix`，用同一批 frontier sweeps 重新評估多組 `frontier_exploratory_r2_gates` 與 `frontier_demo_r2_gates`
- noise frontier 會依 `sigma` 與 `base_kind` 顯示 tier 分布
- noise frontier 會輸出 recommendation，把 tier 失敗轉成下一步實驗標籤，而不是宣稱已經成功
- local strategy probe 會比較目前 RDP、Haar/local basis 與 sparse residual 訊號，但不把任何分支直接提升為 production
- sparse residual frontier 會量測 top-residual correction budgets 相對於 detrended Fourier base 的改善幅度
- sparse residual promotion gate 會沿用 `r2_gate` 與 payload gate 的語言，避免只用 R2 delta 宣稱成功
- sparse residual escalation diagnostic 會對失敗列改用較大的 residual budget 重試，並回報最小可通過 residual budget，用來判斷失敗是預算不足，還是模型家族本身不適合
- residual budget tier 標籤：
  低於 5% 是 `cheap_residual`，5% 到 10% 是 `moderate_residual`，高於 10% 是 `expensive_residual`
- residual escalation recommendation 會把 budget tier 組合轉成下一步實驗標籤，但不宣稱 residual layer 已可 production 化
- residual term-sensitivity evidence 會檢查同一資料集在更高 Fourier terms 下，最小 residual budget 是否下降

## 5) 推進與回退規則

可以推進的條件：

- JSON 與 Markdown 報表能用同一命令重現
- 固定資料集 `steps`、`spikes`、`irregular`、`multiscale`、`smooth` 中至少有非平凡通過案例
- frontier sweep 的 monotonic flag 穩定，至少 80% 列通過
- `tests/test_research_sweep.py` 通過，代表 ratio parser、best-point selection、frontier tier 已被測試保護
- noise frontier 在固定 seed 下可重現，且能記錄高 sigma 時的 `r2_below_gate`
- frontier candidate 同時滿足 fidelity gate 與 storage gate：
  `r2_gate` 與 `frontier_min_payload_ratio`

需要立即回退的情況：

- hard failure 在連續兩個 checkpoint 重複出現
- 使用相同 seed 與相同命令時，frontier best point 發生不可解釋漂移

## 6) 下一步

- 小幅收嚴 gates，避免一次改太多造成不可解釋變化
- 在模型擴張前，先建立低 / 中 / 高 noise budget 分層
- 用 tier matrix 判斷哪一組 exploratory/demo gate 足夠穩定，可以拿來對外報告
- 比較 `smooth`、`spikes`、`multiscale` 三種資料族群下的 noise frontier
- 用 tier-by-sigma 與 tier-by-kind 判斷下一步該優先推 residual、wavelet，或 adaptive segmentation
- 將 `recommended_next_strategy` 視為實驗排程項目，不視為該策略已通過 strict gate
- 用 local strategy probe 表格判斷下一個 checkpoint 應優先做 Haar/local basis 還是 sparse residual
- 用 sparse residual frontier 的最佳點判斷 residual retention 是否能成為下一個被提升的研究分支
- 只有 sparse residual frontier 出現 promotable rows 時，才提升 residual retention；不能只因 R2 delta 為正就提升
- 在更換模型家族前，先檢查 sparse residual escalation；如果失敗列只是在更大的 residual budget 下才通過，就要明確記錄 payload 代價
- 把 `expensive_residual` 視為警訊：在宣稱 residual layer 有效率前，先測更高 terms、local basis、wavelet 或 adaptive segmentation
- 將 residual escalation recommendation 視為實驗排程指標；要經過下一輪 benchmark 驗證後，才能改變預設壓縮行為
- 如果 term sensitivity 顯示同一資料集有改善，要先測更高 terms，再新增新的模型家族
- 準備 renderer-side benchmark：decode cost 與 raster budget 的耦合
