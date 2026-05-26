# RRKAL Visual Compressor

RRKAL Visual Compressor 是一個 Python-first 的視覺壓縮引擎，用來把大型資料集轉成精簡、可重建、可驗證的視覺模型。

它不是一般圖表函式庫，也不是 editor UI。它負責把資料編譯成中介視覺表示，之後再輸出成 SVG、PNG、`demo.py`、metrics，或可被 RRKAL/editor 消費的資產套件。

## 核心概念

```text
large data
  -> analysis
  -> approximation / compression
  -> visual model IR
  -> SVG / demo.py / metrics / package
```

第一個目標資料型態是時間序列：

```text
CSV(time, value)
  -> RDP / Fourier / spline approximation
  -> compact visual model
  -> SVG path
  -> reproducible demo.py
  -> metrics.json
```

## 為什麼需要這個專案

直接把大型資料輸出成 SVG 通常不是好模型：

```text
1,000,000 samples -> 1,000,000 SVG path points
```

這個專案探索的是：

```text
1,000,000 samples -> compact model -> visual reconstruction
```

目標不是無損資料封存，而是「具備可量測保真度的視覺壓縮」。

## MVP 範圍

第一階段只支援：

- CSV 時間序列輸入
- Ramer-Douglas-Peucker polyline simplification
- Fourier approximation
- SVG path 輸出
- `demo.py` 輸出
- `metrics.json` 輸出
- benchmark report，比較大小、誤差、壓縮率

其他想法都先延後。

## 非目標

- 不在這個 repo 做 Qt UI。
- 不在這個 repo 做 Photoshop-like editor。
- 不在這個 repo 整合 Unreal。
- 不宣稱 universal compression。
- 第一階段不做 3D function asset。
- 不保證每個資料集都比 SVG 更小。

## 與其他專案的關係

```text
RRKAL
  管理資料資產、manifest、lineage、install registry

RRKAL Visual Compressor
  把大型資料轉成精簡視覺模型

RRKAL Visual Editor
  開啟 visual model package，處理 styling、annotation、export
```

## 文件

- [docs/CONCEPTUAL_MODEL.zh-TW.md](docs/CONCEPTUAL_MODEL.zh-TW.md)：數學與概念邊界。
- [docs/ARCHITECTURE.zh-TW.md](docs/ARCHITECTURE.zh-TW.md)：架構與 package 邊界。
- [docs/ROADMAP.zh-TW.md](docs/ROADMAP.zh-TW.md)：開發路線。
- [docs/DEVELOPMENT_GOVERNANCE.zh-TW.md](docs/DEVELOPMENT_GOVERNANCE.zh-TW.md)：RRKAL-style 開發治理。
- [docs/AGENT_HANDOFF.zh-TW.md](docs/AGENT_HANDOFF.zh-TW.md)：agent 交接狀態。

## 開發

```powershell
py -m pip install -e .
py -m pytest
vizcompress --help
```

## 第一個可執行命令

產生 synthetic time series，用 RDP 和 Fourier 壓縮，再輸出 SVG、`demo.py`、`metrics.json`：

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --svg-samples 1200 --out smoke_outputs
```

需要傳統 full-point SVG baseline 時，加上 `--direct-svg`：

```powershell
py -m vizcompress.cli build --synthetic 100000 --direct-svg --fourier-terms 96 --out smoke_outputs
```

支援的 synthetic fixtures：

```text
smooth, spikes, steps, chirp, multiscale, noisy, irregular
```

範例：

```powershell
py -m vizcompress.cli build --synthetic 100000 --synthetic-kind spikes --channel --package --out spike_outputs
```

清理資料時，專案把它視為 layered modeling，而不是直接刪除資料：

```powershell
py -m vizcompress.cli build --synthetic 100000 --synthetic-kind noisy --sigma-clip 2.5 --smooth-window 51 --noise-layer-terms 32 --channel --package --out noisy_outputs
```

使用 `--auto-noise-layer` 時，工具會依 residual 分析決定要存 Fourier residual layer，或 sparse residual layer。

建立 channel model：

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --svg-samples 1200 --channel --channel-k 3 --channel-window 501 --out channel_outputs
```

加上 `--package` 會輸出 `.vizasset/.vizretain/.vizclean` 套件：

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --channel --package --out channel_outputs
```

檢查套件是否能重建 renderable arrays：

```powershell
py -m vizcompress.cli inspect channel_outputs/model.vizretain --samples 1200
```

驗證套件 manifest、file hash、model arrays、x-domain encoding 和基本重建路徑：

```powershell
py -m vizcompress.cli verify channel_outputs/model.vizretain --samples 1024
```

如果原始 source 還在，可以在明確 error budget 下，直接驗證 decoded package 是否逼近 source：

```powershell
py -m vizcompress.cli verify channel_outputs/model.vizretain --synthetic 100000 --max-rmse 0.01
```

Build 也可以在 package 旁邊寫出 review packet。這份 `review.json` 會記錄 source fingerprint、verification policy、package self-check、source-fidelity metrics，也會記錄 package bytes 與 source numeric array bytes，作為第一層壓縮證據：

```powershell
py -m vizcompress.cli build --synthetic 100000 --fourier-terms 96 --package --review-packet --review-max-rmse 0.01 --out reviewed_outputs
```

如果 review 不通過時應該讓 build 直接失敗，加入 `--require-review-pass`，而不是只在 `review.json` 寫入 `accepted: false`。

## 狀態

Phase 0/1 已開始。專案目前支援 synthetic/CSV time-series，透過 RDP/Fourier 輸出 SVG、`demo.py`、metrics 和 package。Phase 2 已有 Fourier channel prototype，可表示 center-line 加 residual-band。
