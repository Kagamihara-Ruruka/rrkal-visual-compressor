# Benchmark Evidence

這個資料夾存放小型、可審核、可重跑的 benchmark artifacts。這些檔案不是原始大資料集，而是用來驗證壓縮宣稱的 evidence snapshots。

## Artifacts

- `smooth_100k_terms_sweep.json`：100,000 samples smooth synthetic series，在 Fourier terms `32,64,96` 下的機器可讀 benchmark evidence。
- `smooth_100k_terms_sweep.md`：同一次實驗的人類可讀摘要。
- `smooth_100k_channel_k_sweep.json`：K 值 `2,2.5,3,3.5,4` 的 channel coverage sweep 機器可讀 evidence。
- `smooth_100k_channel_k_sweep.md`：同一次實驗的人類可讀摘要。

## 目前解讀

smooth 100k terms sweep 顯示：在 R2 gate `0.99` 下，所有測試的 Fourier terms 都打贏 SVG.gz 與 source CSV.gz。

但實務甜蜜點不是只看 package 最小。這次實驗中，`32` terms 的 size ratio 最好，但 channel band under-covers；`96` terms 稍大，卻達到 `package_preferred_against_gzip`，所以目前更適合作為 channel-backed visual assets 的預設候選。

channel K sweep 會刻意記錄一個 coverage gate `0.9` 的失敗結果：K 小於 `3` 時覆蓋率不足。這是有用的負面證據，代表目前 smooth 100k fixture 大約需要 K >= `3`，channel model 才比較能防守。
