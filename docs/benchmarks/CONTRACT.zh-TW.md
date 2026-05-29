# Benchmark Contract（繁體中文）

本文件是 CI 與可重現報表的契約規範（資料品質與門檻）。

## 核心規則

對固定 `(synthetic_kind, samples, channel_k)` 與 profile，較高的 Fourier 項目數不應降低 R²：

$$
\forall t_1 < t_2,\quad R^2(t_2)+\epsilon \ge R^2(t_1)
$$

其中 `R^2` 指每列 benchmark 的傅立葉保真度。

驗證器同時檢查：

- `channel_coverage_ratio`（若提供）必須在 `[0, 1]`。
- 比率欄位為正且有限數。
- `summary` 欄位的計數/比值與逐列資料需一致。
- 錯誤訊息包含欄位路徑，例如
  - `row[3].direct_svg_to_package_ratio: must be > 0, got -1.0`
  - `sweep[1].high_fidelity_rows_count: missing`
  - `.../bad.json: row[0].samples: must be a positive integer`

## 風險範圍

- 目標為「目前規格產生的 benchmark JSON」；不作為所有歷史/外部格式的通用驗證器。

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

退出碼：`0` = PASS，`2` = FAIL。

`validate_benchmark_contracts_all.py` 亦支援 `--out`，失敗時輸出 `failed_report`。

`scan_benchmark_fields.py` 提供結構掃描，輸出 mixed/rows/sweep 欄位型態彙整。

`precheck_benchmarks.py` 的回傳 JSON summary 包含：

- `scan_ok`
- `contract_ok`
- `scan`（掃描彙總）
- `contract`（`failed/passed/total/status`）
- `failed_report`
- `status_counts`、`skipped`、`skip_reasons`
- `total_inputs`

## 文件治理

推薦流程：

1. 定義/更新 sweep 腳本與參數
2. 產生 benchmark artifacts
3. 執行 scan 與契約驗證
4. 先預檢，再提交
