# Benchmark 證據檔案

這個資料夾放的是可複現、可審查的 benchmark 證據檔案，皆可由 CLI 重跑。這些檔案不是原始資料集，而是用來驗證壓縮主張的精簡快照（evidence snapshots）。

## 檔案一覽

- `smooth_100k_terms_sweep.json`：`100,000` 筆 smooth 合成序列在 Fourier terms `32,64,96` 下的機器可讀證據。
- `smooth_100k_terms_sweep.md`：同一筆實驗的人類可讀摘要。
- `smooth_100k_channel_k_sweep.json`：channel K 值 `2,2.5,3,3.5,4` 的 coverage sweep 證據。
- `smooth_100k_channel_k_sweep.md`：同一筆實驗的人類可讀摘要。
- `fourier_sweep_16_32_threshold_0995.json`：`16,32` Fourier 項目與 `--defensible-channel-coverage=0.995` 的機器可讀證據。
- `fourier_sweep_16_32_threshold_0995.md`：同一筆實驗的人類可讀摘要。
- `fourier_sweep_10k_16_32_threshold_0995.json`：`10,000` 筆、同條件（16/32）下的機器可讀證據。
- `fourier_sweep_10k_16_32_threshold_0995.md`：同一筆實驗的人類可讀摘要。

## 目前解讀

`smooth_100k` 的 terms sweep 顯示：在 `R2=0.99` 門檻下，所有測試皆優於 SVG.gz 與原始 CSV.gz。  
不過實務上不只看最小 ratio，還要看通道覆蓋是否過關（defensible）：  
此 run 中 `32` terms 有最小 ratio，但 channel band 覆蓋不足；`96` terms 較大，但可達到 `package_preferred_against_gzip`，在通道模型的實務可行性上更有力。

channel K sweep 也刻意保留了 `0.9` coverage gate 失敗範例：K < `3` 時會失敗。這是負面證據，表示該資料型別至少要到 K >= `3` 才能進入可採信區間。

可防禦門檻由 `vizcompress.cli bench` 的
`--defensible-channel-coverage` 參數控制；同一組實驗資料可用不同策略快速重放，例如：

- 寬鬆：`0.9`
- 嚴格：`>= 0.98`

而不必重跑完整模型參數。

## 防禦式證據流程（Defensive Evidence Pattern）

每個 benchmark summary 會輸出兩個門檻值：

- `High-fidelity rows`：`R2 >= 0.99` 的候選列數。  
- `Defensible rows`：在高保真候選中，進一步滿足 `--defensible-channel-coverage` 的列數。

這讓你可以同時報出：

- 壓縮率最優候選（best ratio）  
- 在保真門檻下可採信比例（defensible ratio）

## 執行範例

```bash
py -m vizcompress.cli bench \
  --synthetic-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms-sweep 16,32 \
  --channel \
  --channel-k 3 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --defensible-channel-coverage 0.995 \
  --svg-samples 240 \
  --rdp-epsilon 0.6 \
  --out docs/benchmarks/fourier_sweep_10k_16_32_threshold_0995.json \
  --report-md docs/benchmarks/fourier_sweep_10k_16_32_threshold_0995.md
```

可搭配以下舊版輸出版本對照：

```bash
py -m vizcompress.cli bench \
  --synthetic-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms-sweep 16,32 \
  --channel \
  --channel-k 3 \
  --defensible-channel-coverage 0.995 \
  --svg-samples 240 \
  --out docs/benchmarks/fourier_sweep_16_32_threshold_0995.json \
  --report-md docs/benchmarks/fourier_sweep_16_32_threshold_0995.md
```

### 兩維前沿（terms × channel-K）

```bash
py scripts/run_terms_channel_grid_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --svg-samples 240 \
  --out-json docs/benchmarks/terms_channel_k_grid.json \
  --out-md docs/benchmarks/terms_channel_k_grid.md
```

### 閾值穩定性（terms × channel-K × defensive coverage）

```bash
py scripts/run_terms_channel_threshold_sweep.py \
  --sample-sizes 10000 \
  --synthetic-kind smooth \
  --fourier-terms 16,32,64 \
  --channel-k 2,3,4 \
  --thresholds 0.90,0.92,0.95,0.98,0.995 \
  --channel-window 16 \
  --channel-band-epsilon 0.04 \
  --rdp-epsilon 0.6 \
  --svg-samples 240 \
  --out-json docs/benchmarks/terms_channel_k_threshold_grid.json \
  --out-md docs/benchmarks/terms_channel_k_threshold_grid.md
```
