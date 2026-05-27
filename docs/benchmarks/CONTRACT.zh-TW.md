# Benchmark 合約

本頁定義可重複驗證的規約，作為 CI 與研究成果報告的品質底線。

## 核心條件

固定 `（synthetic_kind, samples, channel_k）` 與同一 profile 下，增大 Fourier 項數不應降低保真度：

$$
\forall t_1 < t_2,\quad R^2(t_2)+\epsilon \ge R^2(t_1)
$$

其中 `R²` 指每列 row 的 Fourier 擬合分數。

驗證器也會檢查：

- `channel_coverage_ratio` 若存在，需落在 `[0,1]`。
- 各壓縮比欄位為正數且有限值。
- summary 的各類計數要和 row 級結果一致。

## 使用範圍

- 輸入為本專案目前 sweep 腳本輸出的 benchmark JSON。
- 這是**可重現性/一致性**合約，不是通用數學普適性保證。

## CLI

```bash
py scripts/validate_benchmark_contracts.py docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json
```

回傳值：

- `0`: PASS
- `2`: FAIL

## 為什麼要做

完整流程：
1. 定義壓縮表示族群
2. 指定可量測收斂條件
3. 執行可重現 sweep
4. 對 JSON 做合約驗證

能避免本機與雲端/遠端節點對同一資料有不同解讀。
