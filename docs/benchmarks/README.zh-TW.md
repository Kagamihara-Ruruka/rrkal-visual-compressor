# 基準測試彙整（Benchmark Evidence）

本資料夾保留可重現的壓縮實驗快照，用於支撐壓縮主張與品質閘道門檻（gate policy）。

## 主要用途

- 提供機器可讀的 JSON 證據，記錄在不同參數下的壓縮比、R²、通道覆蓋率與建議策略。
- 提供可讀的 Markdown 報告，讓團隊與主管快速做決策。
- 以固定參數命名（含 `sample_sizes`, `thresholds`, `fourier_terms`, `channel_k`）保證可追溯。

## 最近的 gate 快照

- `terms_channel_kind_threshold_grid_10k_gate.json`
- `terms_channel_kind_threshold_grid_10k_gate.md`

這份快照是「10,000 點 + 全部合成族群 + kind/sweep」的版本，並開啟 `--require-svg-gzip-win` 與 `--min-defensible-ratio 0.2`，可直接當成「是否通過可交付門檻」的監控依據。

## 關鍵欄位（英文原名）

- `defensible_rows_count`：在 `R²>=0.99` 且通道覆蓋率達門檻的列數。
- `defensible_rows_ratio`：上面列數除以高保真列數。
- `package_wins_against_direct_svg_gzip_count`：模型套件比直接 SVG.gz 更小的列數（比率 > 1）。
- `package_wins_against_source_csv_gzip_count`：模型套件比來源 CSV.gz 更小的列數（比率 > 1）。
- `benchmark_gate.ok`：是否通過所有門檻條件。

## 指令範例

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

## English

For the English version, see `README.md`.
