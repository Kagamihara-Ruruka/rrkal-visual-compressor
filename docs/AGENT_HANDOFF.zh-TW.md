# Agent Handoff

## 任務

先建立小型、可測試的 visual compression engine，再逐步擴大範圍。

## 硬邊界

- 不在這裡加入 Qt。
- 不在這裡建立 visual editor。
- 不在這裡整合 Unreal。
- 不宣稱 universal compression。
- 保持此 package 可被 RRKAL 和 editor import。

## 目前工作區規則

- 在 `K:\Codex\2026-05-26\qt-vispy\rrkal-visual-compressor` 開發。
- 使用 `C:\Users\lyn59\Documents\Codex\2026-05-26\qt-vispy\rrkal-visual-compressor` 作為本地測試副本。
- 從 cloud workspace push commits 到 GitHub `origin/main`。

## 目前狀態

已實作主線：

- time-series analyzers 與 synthetic fixtures
- RDP 與 Fourier compressors
- Fourier channel model
- cleaning as layered modeling，不做破壞式刪除
- sparse residual layer 與 Fourier residual noise layer
- `.vizretain`、`.vizclean`、neutral `.vizasset` package family
- Fourier、channel、sparse residual、noise layers 的 package readback
- irregular x-domain handling，支援 preserve、compressed、auto policies
- benchmark matrix，含 per-kind summaries 與 recommendation labels
- `build`、`bench`、`recommend`、`inspect`、`verify` CLI commands
- source-backed package fidelity verification，支援 optional RMSE/MAE/max-error budgets
- `review.json` packet generation，包含 source fingerprints 與 accepted metrics
- `--require-review-pass` build gate，可拒絕超出 review budgets 的 package
- `compare` CLI，可對既有 package 產生 raw/gzip baseline size evidence
- benchmark rows 會包含 LTTB downsampling baseline metrics
- 繁中版文件：README、architecture、conceptual model、roadmap、governance、handoff

目前本地驗證命令：

```powershell
py -m pytest -q
```

最近已知通過數：`36 passed`。

## 原始第一任務

把 `proof_vectorization.py` port 到：

```text
src/vizcompress/compressors.py
src/vizcompress/exporters.py
src/vizcompress/metrics.py
tests/test_timeseries_compression.py
```

## 第一個 PR 的 Definition Of Done

- `py -m pytest` passes。
- CLI 可以從 synthetic data 產生 SVG 與 metrics。
- README quickstart works。
- 沒有 UI dependencies。

## 設計原則

Compressed model 是 visual reconstruction 的 source。SVG 是 export target，不是 internal truth。

Residuals 不會自動丟棄。Retained package 會保留 residual layers；clean package 只輸出 cleaned main signal。
