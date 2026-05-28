# MVP 檢查點

這個 repo 現在具備一條命令即可執行的時間序列視覺壓縮 MVP 流程。

## 指令

```powershell
py -m vizcompress.cli mvp --samples 20000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 1200 --out mvp_outputs --min-fourier-r2 0.95
```

## 它證明了什麼

這條命令會跑完最小產品閉環：

- 產生 synthetic 大型時間序列
- 輸出 direct SVG、RDP SVG、Fourier SVG、channel SVG、`demo.py`、`metrics.json`
- 寫出 `.vizretain` package
- 驗證 package manifest、hash、model arrays 與 reconstruction
- 驗證重建結果對 source 的逼近程度
- 跑一個小型 benchmark，對照 direct SVG.gz 與估算 CSV.gz
- 寫出 `mvp_summary.json`、`benchmark.json` 與 `benchmark.md`

## 最新 Smoke Result

執行日期：2026-05-28

- dataset：`spikes`
- samples：`20000`
- Fourier terms：`64`
- status：`pass`
- Fourier R2：`0.987209884017974`
- package bytes：`74688`
- direct SVG.gz bytes：`105679`
- estimated source CSV.gz bytes：`333446`
- direct SVG.gz to package ratio：`1.4149394815766925`
- source CSV.gz to package ratio：`4.464519065981149`
- recommendation：`package_preferred`
- gzip recommendation：`package_preferred_against_gzip`

## MVP 邊界

這是視覺壓縮 MVP，不是 universal compressor。

可以主張：

- 專案可以把時間序列編譯成精簡視覺資產
- 資產可以被驗證與重建
- benchmark evidence 可以指出 package 何時勝過 SVG.gz 或 CSV.gz

不能主張：

- 每種資料都會壓得好
- 目前 Fourier 路徑已解決所有局部突變問題
- 這已經是通用 image/video/3D asset standard

## 下一個 Gate

在宣稱 MVP 穩定前，保持以下 gate 通過：

```powershell
py -m pytest
py -m vizcompress.cli mvp --samples 20000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 1200 --out mvp_outputs --min-fourier-r2 0.95
```
