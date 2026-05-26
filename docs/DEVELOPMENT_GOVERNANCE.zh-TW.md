# 開發治理

這個 repository 採用 RRKAL-style 開發紀律：保持核心模型小、把 source truth 與 projections 分開，並讓每個功能都能透過文件化命令測試。

## Source Of Truth

- Raw input data 是 read-only。
- Compressed visual models 是 reconstruction 的 source。
- SVG、demo scripts、PNGs、editor views 都是 exports，不是 canonical data。
- 未來 `.vizasset` packages 必須把 source metadata、processing parameters、fidelity metrics、lineage 放在一起。

## MVP 邊界

目前主線是：

```text
time series -> compact visual model -> SVG/demo.py/metrics
```

只有能改善這條 flow 的功能才應該進 mainline。2D shape fields、void/material assets、3D implicit assets、Unreal projection、editor UI 等長期想法，在有 CLI path 與 tests 前，應留在 docs、contracts 或 isolated stubs。

## 專案邊界

- 本 repo 負責 compression algorithms、visual model contracts、metrics、export preparation。
- Editor repo 負責 interaction、styling、annotation、Photoshop-like UI。
- RRKAL 負責 asset registry、source manifests、install state、broader data lineage。
- Runtime engines 是 exported packages 的 consumers，不是 model owners。

## 工程規則

- 主要開發位置：
  `K:\Codex\2026-05-26\qt-vispy\rrkal-visual-compressor`
- 本機測試位置：
  `C:\Users\lyn59\Documents\Codex\2026-05-26\qt-vispy`
  是 test/verification copy，不是 canonical development copy。
- GitHub 必須從 cloud workspace 同步；cloud commits 後 push `main` 到 `origin`。
- 需要本機測試時，把 cloud state copy/pull 到 local workspace，先本機測試，再從 cloud workspace commit/push。
- 每個 user-facing feature 都需要 CLI route、tests、metrics output。
- 不要為核心行為加入 hidden one-off scripts。
- 不要 commit generated outputs、private datasets、caches、local runtime artifacts。
- 優先使用小型 typed modules，不要直接把 sample code 貼進主線。
- 只要變更影響 usage、architecture、roadmap、agent handoff，就更新 docs。
- 把 compression claims 當成可量測假說：回報 sample count、parameter count、error、coverage，不只依靠理論。

## Research Gate

研究想法升級成實作前，先回答：

1. 它服務哪個 MVP segment？
2. 哪個 CLI command 會執行它？
3. 哪個 test 證明它有效？
4. 哪些 metrics 顯示它贏或輸？
5. 如果移除它，現在 MVP 會不會壞？

如果最後一題答案是「不會」，就先把它留在 documented research boundary，直到 mainline 真的需要。
