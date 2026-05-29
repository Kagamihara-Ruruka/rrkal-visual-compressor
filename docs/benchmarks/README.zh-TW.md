# Benchmark Evidence（繁體中文）

本目錄包含視覺壓縮 benchmark 的 JSON 報表與對應 Markdown 摘要，主要作為研究結果與回歸門檻的證據。

## 核心文件

- `smooth_100k_terms_sweep.json` / `smooth_100k_terms_sweep.md`
- `smooth_100k_channel_k_sweep.json` / `smooth_100k_channel_k_sweep.md`
- `fourier_sweep_16_32_threshold_0995.json` / `fourier_sweep_16_32_threshold_0995.md`
- `fourier_sweep_10k_16_32_threshold_0995.json` / `fourier_sweep_10k_16_32_threshold_0995.md`
- `defensible_threshold_sweep_10k_16_terms.json` / `defensible_threshold_sweep_10k_16_terms.md`
- `terms_channel_k_grid.json` / `terms_channel_k_grid.md`
- `terms_channel_k_threshold_grid.json` / `terms_channel_k_threshold_grid.md`
- `terms_channel_kind_threshold_grid.json` / `terms_channel_kind_threshold_grid.md`
- `terms_channel_kind_threshold_grid_10k.json` / `terms_channel_kind_threshold_grid_10k.md`
- `terms_channel_kind_threshold_grid_10k_gate.json` / `terms_channel_kind_threshold_grid_10k_gate.md`
- `terms_channel_kind_threshold_grid_5k_hard.json` / `terms_channel_kind_threshold_grid_5k_hard.md`
- `terms_channel_kind_threshold_grid_5k_noiseclean.json` / `terms_channel_kind_threshold_grid_5k_noiseclean.md`
- `defensible_hardening_report_terms64.json` / `defensible_hardening_report_terms64.md`
- `README.md`

## 主要欄位

- `defensible_rows_count`：滿足防禦門檻（例如 R2 >= 0.99）的列數。
- `defensible_rows_ratio`：`defensible_rows_count / high_fidelity_rows_count`。
- `package_wins_against_direct_svg_gzip_count`：`package / direct_svg_gzip` 有優勢的列數。
- `package_wins_against_source_csv_gzip_count`：`package / source_csv_gzip` 有優勢的列數。
- `benchmark_gate.ok`：該報表是否通過門檻。
- `defensible_hardening_report_terms64`：`spikes` 族群下對 `16/32/64` 項的殘差改善曲線。

## 產生 benchmark 的範例

```bash
py scripts/run_terms_channel_kind_threshold_sweep.py `
  --sample-sizes 10000 `
  --synthetic-kinds all `
  --fourier-terms 16,32,64 `
  --channel-k 2,3,4 `
  --channel-window 16 `
  --channel-band-epsilon 0.04 `
  --rdp-epsilon 0.6 `
  --thresholds 0.90,0.92,0.95,0.98 `
  --svg-samples 240 `
  --require-svg-gzip-win `
  --min-defensible-ratio 0.2 `
  --out-json docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json `
  --out-md docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.md
```

## 契約驗證

```bash
py scripts/validate_benchmark_contracts.py `
  docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json `
  --out docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate_contract.json
```

### 驗證規則（摘要）

- 相同 `(synthetic_kind, samples, channel_k)` 下，`fourier_terms` 遞增不應使 `fourier_r2` 下降。
- `channel_coverage_ratio`（若存在）必須在 `[0, 1]`。
- 比率欄位必須是正且有限數。
- `summary` 與 row 級指標需一致。

### 全域掃描與嚴格驗證

```bash
py scripts/scan_benchmark_fields.py --root docs/benchmarks --pattern "*.json" --out docs/benchmarks/scan_report.json
py scripts/validate_benchmark_contracts_all.py --root docs/benchmarks --out docs/benchmarks/contract_matrix_latest.json
```

回傳 `PASS/FAIL`，並輸出逐檔錯誤明細。

### 遷移 legacy hardening 報告（建議先 dry-run）

若資料夾中仍有舊版 `defensible_hardening_report*.json`，可先做一次預覽：

```bash
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run
```

確認轉換行為無誤後，再移除 `--dry-run` 直接輸出對應 `*_contract.json`，並可見每列轉換結果會保留 `_legacy_source` / `_legacy_defensible` 欄位方便追溯。

## 合併前 precheck（強制）

本機進行人工推進或上傳 benchmark 成果前，必須先跑：

```bash
py scripts/precheck_benchmarks.py `
  --root docs/benchmarks `
  --pattern "*.json" `
  --scan-out docs/benchmarks/scan_report.json `
  --contract-out docs/benchmarks/contract_matrix_precheck.json `
  --fail-on-scan-warning
```

### precheck 輸出欄位

- `scan_ok`：欄位結構掃描是否成功。
- `contract_ok`：契約驗證是否成功。
- `scan`：欄位掃描彙總。
- `contract`：`failed/passed/total/status`。
- `failed_report`：契約失敗時的報告路徑（若 `--contract-out` 啟用）。
- `status_counts`：`PASS`/`FAIL`/`SKIP` 各類數量。
- `skipped`：未參與嚴格驗證的非契約/legacy 檔數。
- `skip_reasons`：`SKIP` 的原因映射。
- `total_inputs`：本次掃描的檔案總數。

## 文件對應

- CI 使用流程可見 `.github/workflows/benchmarks-precheck.yml`。
- 其他欄位定義與契約規則請同步閱讀 [docs/benchmarks/CONTRACT.zh-TW.md] 和 [docs/benchmarks/CONTRACT.md]。
