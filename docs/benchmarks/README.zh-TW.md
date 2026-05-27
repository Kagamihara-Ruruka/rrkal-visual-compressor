# 基準測試紀錄（Benchmark Evidence）

此資料夾放置可重複驗證的小型壓縮實驗快照（`JSON`）與對應報告（`Markdown`），用於支撐壓縮與門檻政策（gate policy）的論證。

## 藝術資源

- `smooth_100k_terms_sweep.json`：100,000 點平滑訊號、頻率項 32/64/96 的 sweep。
- `smooth_100k_terms_sweep.md`：同上 human-readable 摘要。
- `smooth_100k_channel_k_sweep.json`：`K` 值 2/2.5/3/3.5/4 sweep。
- `smooth_100k_channel_k_sweep.md`：同上摘要。
- `fourier_sweep_16_32_threshold_0995.json`：10,000 點 `fourier_terms` 16 與 32，覆蓋閾值 `0.995`。
- `fourier_sweep_16_32_threshold_0995.md`：同上摘要。
- `fourier_sweep_10k_16_32_threshold_0995.json`：帶有額外視窗與 ε 設定的壓力測試。
- `fourier_sweep_10k_16_32_threshold_0995.md`：同上摘要。
- `defensible_threshold_sweep_10k_16_terms.json`：16 項 `terms` 的 coverage threshold 敏感度測試。
- `defensible_threshold_sweep_10k_16_terms.md`：同上摘要。
- `terms_channel_k_grid.json`：`terms` 與 `channel_k` 網格 sweep。
- `terms_channel_k_grid.md`：同上摘要。
- `terms_channel_k_threshold_grid.json`：`terms`×`channel_k`×`threshold` sweep。
- `terms_channel_k_threshold_grid.md`：同上摘要。
- `terms_channel_kind_threshold_grid.json`：多種資料型別之穩健性比較。
- `terms_channel_kind_threshold_grid.md`：同上摘要。
- `terms_channel_kind_threshold_grid_10k.json` / `_10k.md`：10k 點門檻資料（未加閘門）。
- `terms_channel_kind_threshold_grid_10k_gate.json` / `_10k_gate.md`：10k 點門檻資料（加上渲染門檻）。
- `terms_channel_kind_threshold_grid_5k_hard.json` / `_5k_hard.md`：含噪、突變、階梯的堅固訊號穩健性探測。
- `terms_channel_kind_threshold_grid_5k_noiseclean.json` / `_5k_noiseclean.md`：`--sigma-clip 2.5 --auto-noise-layer` 的去雜訊版本。
- `README.md`：英文版。

## 目前觀察重點

- `defensible_rows_count`：高保真（`R2>=0.99`）且通過通道覆蓋率閾值的候選列數。
- `defensible_rows_ratio`：上述可用列的比例。
- `package_wins_against_direct_svg_gzip_count`：壓縮套件比 `SVG.gz` 小的案例數。
- `package_wins_against_source_csv_gzip_count`：壓縮套件比原始 `CSV.gz` 小的案例數。
- `benchmark_gate.ok`：門檻是否同時通過。

## 指令參考

```bash
py scripts/run_terms_channel_kind_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kinds all \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --thresholds 0.90,0.92,0.95,0.98 \
  --svg-samples 240 \
  --require-svg-gzip-win \
  --min-defensible-ratio 0.2 \
  --out-json docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json \
  --out-md docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.md
```

### 合約驗證

使用基準合約驗證器確認欄位一致性，避免不同 sweep 設定下拿到不可比對的結果：

```bash
py scripts/validate_benchmark_contracts.py \
  docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate.json \
  --out docs/benchmarks/terms_channel_kind_threshold_grid_10k_gate_contract.json
```

合約檢核包含：

- 對固定 `(synthetic_kind, samples, channel_k)`，`fourier_r2` 不隨項數下降。
- 覆蓋率存在時，必須落在 `[0,1]`。
- 壓縮比欄位必須是有限且大於 0 的值。
- summary 的行為欄位要可由 row-level 計算還原一致。

一次檢查整個資料夾全部 JSON：

```bash
py scripts/validate_benchmark_contracts_all.py \
  --root docs/benchmarks \
  --out docs/benchmarks/contract_matrix_latest.json
```

腳本會逐檔輸出 `PASS/FAIL`，有任一失敗會以非 0 離開碼回報。

## 英文版

See `README.md`.

## 跨機器重現性檢核（推薦）

建議使用 `check_benchmark_parity.py` 除了比對雜湊之外，還能比對關鍵邏輯欄位（`benchmark_gate`、`rows_by_kind`）。  
流程：

1. 於 `K:` 與 `C:` 以相同參數輸出同名 JSON（含 `--out-json`）。
2. 再比較兩個 JSON：

```bash
py scripts/check_benchmark_parity.py \
  --left docs/benchmarks/ci_terms_channel_kind_threshold_sweep_k.json \
  --right docs/benchmarks/ci_terms_channel_kind_threshold_sweep_c.json
```

這個工具會輸出：

- `hash: MATCH`（表示二進位完全一致）
- `logical_signature: PASS`（表示關鍵欄位邏輯一致）

可用單元測試直接驗證這個比對邏輯：

```bash
py -m pytest tests/test_benchmark_parity.py
```

透過測試可確認：

- 完全相同檔案會回傳 `hash: MATCH`
- 只有 metadata 差異時仍為 `logical_signature: PASS`
- 關鍵欄位差異會回傳 `logical_signature: FAIL`
