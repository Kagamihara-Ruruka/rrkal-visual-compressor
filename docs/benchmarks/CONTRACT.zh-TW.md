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
- 每筆錯誤都會附上欄位路徑前綴，例如：
  - `row[<index>].<field>: <訊息>`
  - `sweep[<index>].<field>: <訊息>`

範例：

- `row[3].direct_svg_to_package_ratio: must be >0, got -1.0`
- `row[3].direct_svg_gzip_to_package_ratio: must be >0, got -1.0`
- `sweep[1].high_fidelity_rows_count: missing`
- `docs/benchmarks/.../bad.json: row[0].samples: must be a positive integer, got -1`

批次輸入驗證器（`validate_benchmark_contracts_all.py`）額外支援
`--out`，當任一檔案失敗時會在輸出 JSON 寫入 `failed_report`。

在 `status` 聚合上，`validate_benchmark_contracts_all.py` 將無合約 / legacy 內容判定為 `SKIP`（非 fail）：

- `total_inputs`: 掃描到的輸入檔數
- `total` / `passed` / `failed` / `skipped`：依 row 狀態彙總
- `status_counts`: `PASS`、`FAIL`、`SKIP` 次數
- `skip_reasons`: 目前僅使用 `legacy_or_non_contract_payload`
- `rows[].skip_reason`: legacy 或非合約 row 的原因

`rows[].status` 在以下情況會是 `SKIP`：summary 缺少 `high_fidelity_rows_count` 或 `defensible_rows_count`。

預設會排除以下報告檔案名稱，避免掃描到歷史輸出：

- `scan_report*.json`
- `contract_matrix*.json`

## 使用範圍

- 輸入為本專案目前 sweep 腳本輸出的 benchmark JSON。
- 這是**可重現性/一致性**合約，不是通用數學普適性保證。

## CLI

```bash
py scripts/validate_benchmark_contracts.py docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json
py scripts/validate_benchmark_contracts_all.py --root docs/benchmarks
py scripts/scan_benchmark_fields.py docs/benchmarks
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run
py scripts/precheck_benchmarks.py \
  --root docs/benchmarks \
  --pattern "*.json" \
  --scan-out docs/benchmarks/scan_report.json \
  --contract-out docs/benchmarks/contract_matrix_precheck.json \
  --fail-on-scan-warning
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
