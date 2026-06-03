# CompressionContractSpec 能力維度草案（中期設計）

本文檔為 docs/contract-design-only 草案：建立 `.vizasset` 相關能力的契約語彙，供未來 c_1 / c_3 與 c_2 間對齊，不承諾跨 repo 實作，不新增產品整合。

## TL;DR

- `.vizasset` 被視為「壓縮結果的可驗證契約載體」，非純輸出檔。
- visual-compressor 維持 `.vizasset` 的核心責任：建模、預覽、驗證、重建與評測能力。
- `verify` / `inspect` / `reconstruct` / `bench` 只證明既有契約欄位；不代表與 displaytools / Core 的跨模組契約已成立。
- `CompressionContractSpec` 先以文檔層定義，供未來可選擇性對 `Core`、`Display` 開放消費。
- 本文件不新增任何實作、schema migration 或整合邏輯。

## Compression algorithm as contract

中期方向是：壓縮算法結果不再只看作「模型壓縮過程」，而是看作可互換、可驗證、可消費的資料合約。

### 合約核心理念

- **能力宣告（capability declaration）**：package 要宣告可重建、可預覽、可評測、可重建品質保證的邊界。
- **可驗證性（verifiability）**：每個能力維度都能透過既有指令行為被證明或失敗。
- **可協作性（collaboration-ready）**：`Core` / `Display` 只作為未來消費者，透過欄位語義取用，不反向驅動目前流程。
- **無綁定性（no-tooling lock-in）**：不將視覺化工具鏈（例如 displaytools）硬綁為必需條件。

## What `.vizasset` promises

- 以 manifest（`asset.json`）描述壓縮結果與重建前提（schema / compatibility / model / metrics / files）。
- 可被 `inspect` 與 `verify` 識別並進行品質與結構檢查。
- 可被 `reconstruct` 重建主要訊號輸出與降維回放資訊。
- 可被 `bench/compare/recommend` 參與封包級與基線比較。
- 對外部工具以「明確欄位 + 行為邏輯」形成契約，而非要求外部工具知道實作細節。

## What `verify / inspect / reconstruct / benchmark` 各自證明什麼

- `verify`
  - 驗證 manifest 完整性、欄位一致性與檔案可讀性。
  - 驗證 `.vizasset` 的資料結構是否符合預期重建流程。
  - 輸出可作為「契約是否成立」的第一道門檻。

- `inspect`
  - 讀取 manifest 並檢驗可重建路徑、樣本、重建報告與錯誤訊號。
  - 提供人類可讀/工具可讀的觀察資料，作為審閱與排障依據。

- `reconstruct`
  - 證明重建流程在特定重建模式下可執行且輸出結果有效。
  - 不同 `reconstruct` 選項對應不同能力維度（例如是否含 sparse/residual/noise）。

- `bench`（含 `video-bench` / `precheck-benchmarks`）
  - 證明壓縮表現、尺寸與品質 trade-off 的可比較性。
  - 提供不同壓縮家族在既定 metric 下可再現的度量結果。

## What Core may consume later

- 壓縮後包是否可重建、是否可回放、對品質指標的保證。
- 容量、容錯、壓縮家族、重建模式、通道、誤差型態等 metadata，作為後續資源調度與回傳策略依據。
- 錯誤指標摘要與重建可用性，用於核心層的可視化管線決策。

> 僅為概念可消費方向；非承諾實作。

## What Display may consume later

- `.vizasset` 是否具備 preview/ reconstructable 的能力訊息。
- 是否有足夠證據支援可視化顯示策略（例如預覽與重建輸出一致度）。
- 檔案結構與 schema 規格，作為 display 端讀取與降級策略的未來輸入。

> 仍不涉及任何 displaytools 介接。

## What must remain owned by visual-compressor

- `CompressionContractSpec` 欄位語彙的版本管理。
- `asset.json` 的主權欄位定義與兼容條件。
- `verify` / `inspect` / `reconstruct` / `benchmark` 的行為邏輯與回報口徑。
- 預設質控與壓縮品質判斷門檻（在既有 benchmark/contract 範圍內）。

## What must not be integrated yet

- 不得以 `SkinAsset` / `RendererSkinAsset` 作為預設整合目標。
- 不得在本輪引入 `RRKAL_displaytools` 或 `RRKAL Core` 端實作變更。
- 不得以 `.npz` 假設替代 manifest 或驗證流程。
- 不得提交與跨 repo import/export 相關的實作。
- 不得宣告「已具備 production-safe」或「100% integration ready」。

## Candidate capability dimensions

| Dimension | Candidate values | Why it matters | Consumer | Risk |
|---|---|---|---|---|
| `asset_kind` | `timeseries`, `video`, `image`, `future.generic` | 決定重建路徑、預覽格式、驗證欄位 | visual-compressor, Core, Display | 錯誤歸類導致重建失敗 |
| `reconstruction_mode` | `full`, `reduced`, `approximate`, `signal-only` | 決定可重建精度與可視化可信度 | reconstruct / verify / Core | 模式混用造成品質誤判 |
| `error_metric_profile` | `rmse`, `mae`, `max-error`, `max-x-error`, `psnr`(future) | 明確對齊誤差解讀邏輯與門檻 | verify / bench | 指標名稱歧義導致錯誤比較 |
| `compression_family` | `spatial_fourier`, `spline`, `hybrid`, `future.custom` | 區分算法特性與運算需求 | visual-compressor, Core | 將算法能力誤當作通用能力 |
| `payload_shape` | `signal-1d`, `signal-2d`, `sequence`, `multi-channel` | 決定 payload 取樣、還原與記憶體約束 | reconstruct / inspect | 形狀不一致造成重建錯位 |
| `preview_support` | `svg`, `png`, `none` | 協定是否可供快速驗證與快速 diff | inspect / verify / Display（未來） | 僅支援單一預覽導致回歸難察覺 |
| `benchmark_support` | `none`, `basic`, `extended`, `video` | 決定可比對性與性能分析深度 | bench / recommend / core-planning | 過度報告導致 benchmark overclaim |
| `evidence_output` | `metrics.json`, `review.json`, `scan_report`, `benchmark_report` | 讓消費端得知測試結果來源與格式 | verify / inspect / o_1 / CI | 輸出缺失阻斷自動化評估 |
| `edge_low_compute_support` | `cpu-basic`, `cpu-lowmem`, `gpu-optional`, `none` | 定義壓縮/重建在受限環境可用性 | core-planning / Display（未來） | 不支援邊緣端，誤導部署策略 |
| `schema_compatibility` | `v0.1`, `v0.2`, `future-compat` | 保障契約漂移與版本演進邏輯 | verify / inspect / future parser | 版本漂移導致無法解析 |

## Draft CompressionContractSpec（pseudo-structure）

```text
{
  "contract_id": "ccs:vizasset:timeseries:reconstructable:v0.2",
  "schema_version": "0.2",
  "asset_kind": "timeseries",
  "compression_family": "spatial_fourier",
  "reconstruct_modes": ["full", "signal-only"],
  "error_metrics": ["rmse", "mae", "max-error"],
  "evidence_outputs": ["metrics.json", "review.json", "contract_matrix"],
  "compatibility_profile": {
    "preview_only": true,
    "reconstructable": true,
    "renderer_native": false,
    "requires": {
      "numpy": ">=1.24",
      "rrkal_visual_compressor": ">=0.1",
      "displaytools": false,
      "rrkal_core": false
    }
  },
  "consumer_hints": {
    "core": {
      "admissible_modes": ["reconstruct", "inspect"],
      "risk": "contract-boundary"
    },
    "display": {
      "admissible_modes": ["inspect", "benchmark-lite"],
      "risk": "viewer-consistency"
    },
    "c2_only": {
      "owns": [
        "schema_version",
        "compatibility_profile",
        "verify_rules",
        "benchmark_contract"
      ]
    }
  },
  "notes": [
    "preview / reconstruct 能力可獨立演進；不保證同一 model payload 即支援全部重建模式"
  ]
}
```

> 上述為草案結構；欄位名稱與值需由下一輪以既有實作 evidence 對齊確認後再落版。

## Risk register (for c_2 docs/contracts)

| Risk | Why it matters | Mitigation |
|---|---|---|
| schema drift | schema 版本或欄位變更卻未同步驗證，將破壞 `verify`/`inspect` | 明確定義 `schema_version` 與變更公告，先行做 docs/drift checks |
| overfitting to displaytools | 將能力宣告綁死於特定 display 工具，失去可移植性 | 在 `compatibility_profile.requires` 保持 `displaytools: false`，改以能力維度描述 |
| compression as only preprocessor | 把壓縮誤認為只是前處理，忽略契約可驗證性與再現性 | 將 `proof commands` 與 `evidence_outputs` 放入契約核心 |
| premature cross-repo import | 未完成契約一致性前就做跨 repo 匯入導致難回滾 | 文件明確標註「設計草案」，所有實作待授權 |
| benchmark overclaim | 未比較環境條件下仍主張可比性 | 分離 `benchmark_support` 與 `evidence_output`，明示可比性範圍 |
| generated artifact pollution | 在 repo 內混入中間檔導致可重現性下降 | docs-only slice 僅記錄，不產生 artifact；build artifact 仍走既有流程 |
| private payload / `.npz` assumptions | 依賴私有 payload 結構導致解析器不穩 | 在契約中保留 `payload_shape` 與 `compatibility_profile`，避免硬編碼假設 |

## CapabilityCode 概念討論（附錄）

- 可選方向：未來在 `contract_id` 或 `consumer_hints` 中加入穩定可比對的能力碼（例如 `cc.cap.timeseries.reconstructable.full`）：
  - 優點：跨模組路由更清楚。
  - 風險：若能力碼先行落地且未穩定，會鎖死設計。
  - 建議：先把能力維度與欄位一致性對齊後，再討論實際能力碼語彙與版本治理。

## Stability check for capability addressing

目前不實作 4-bit addressing；僅確認以下條件是否足夠穩定做為未來位址化討論：

1. 每個主要維度都能被 CLI 命令體系逐一驗證（至少 `verify` / `inspect` / `benchmark`）；
2. `compatibility_profile` 與 `consumer_hints` 可獨立判讀且不依賴 displaytools；
3. 同一能力維度在文檔與 artifacts 之間可雙向追蹤；
4. 不跨越跨 repo integration 或實作承諾；
5. 任何可消費宣告都保留 `risk` 欄位，避免隱性耦合。

若以上 1~5 通過，才可啟動下一輪能力碼方案設計。

