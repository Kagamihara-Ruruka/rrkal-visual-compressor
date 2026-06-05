# Compression ContractCard Evidence Taxonomy & SOP Drift Audit（c_2）

本文件是 `L2` 限縮的分支盤點結果：只整理 `.vizasset`/CLI/測試可證明的 ContractCard 供應欄位，並列出 startup / governance 文件漂移。

## 分類邊界

- 本盤點為 docs-only，無程式碼/CLI 行為或 schema 變更。
- 不建立跨 repo integration 承諾。
- 不變更 `RRKAL_displaytools`、`RRKAL Core`、`SkinAsset / RendererSkinAsset` 路徑。
- 僅做文件一致性與可驗證性對照，供 `c_1 / c_3` 接續規劃。

## A. ContractCard 可用欄位盤點（c_2 分類）

### verified（現況可驗證）

依據：
- `src/vizcompress/packages.py`（manifest 形狀與驗證規則）
- `src/vizcompress/cli.py`（命令輸出）
- `src/vizcompress/bench_precheck.py`、`tests/test_cli_smoke.py`、`tests/test_precheck_benchmarks.py`（命令與測試契據）

| 欄位 | 來源證據 | 為何可視為 verified |
|---|---|---|
| `schema_version` | `asset.json` / `compatibility` 驗證邏輯 | `packages.py` 強制 `ASSET_SCHEMA_VERSION = "0.2"`，`validate_vizasset` 校驗。 |
| `asset_kind` | `asset_type` / `inspect` 輸出 | `inspect`/`verify` 已回報 `asset_type`，目前對齊 `rrkal.visual_compressor.timeseries`。 |
| `compression_family` | `model.primary_method` / `model.methods` | manifest 固定輸出壓縮主方法，`inspect`/`reconstruct` 可關聯。 |
| `reconstruct_modes` | `compatibility.renderability` + `reconstruct` 參數 | 命令行行為可切換 `full/signal-only/sparse/noise/retained`。 |
| `error_metrics` | `metrics` 區塊 + metrics/report 輸出 | CLI `verify/inspect` 可輸出並可被測試讀取。 |
| `evidence_outputs` | `files` block、`metrics.json`、`review.json`、bench/scan/contract report | manifest/CLI 明確記錄輸出集合，測試可驗證 JSON key。 |
| `compatibility_profile` | `compatibility` block + 驗證 schema | `compatibility.schema`、`renderability`、`package_kind` 在 manifest 內。 |
| `generated_at` | `generated_at_utc` | manifest/review 具時間戳字段。 |
| `tool_version` | `generated_by.version` + `review` metadata | 由 `vizcompress.__version__` 與 `reviews.py` 寫入。 |

### declared-only（僅草案宣告，尚未成為穩定對外消費欄位）

| 欄位 | 來源 | 限制 |
|---|---|---|
| `contract_id` | 草案與欄位建議中使用 | 尚未作為 manifest/review 的穩定發佈主鍵。 |
| `consumer_hints` | 規格草案建議段落 | 僅治理引導資訊，未形成 parser 契約。 |
| `payload_shape` | `source.sample_count`/`source.kind` 部分映射 | 尚未有完整泛型 `dim / channels / dtype` 形式。 |
| `benchmark_profile` | `bench`/`precheck-benchmarks` 輸出建議 | 尚未綁定為 ContractCard 核心欄位。 |
| `source_manifest_hash` | 待規劃字段 | 尚未全域輸出與驗證 gate 對齊。 |

### unsafe downstream fields（暫不建議下游視為正式可消費）

| 欄位 | 風險 |
|---|---|
| `model.primary_method` 原生字串 | 目前缺少可互操作版本化詞彙，跨版本可能漂移。 |
| `model.methods` 詳細列表 | 欄位名義上偏實作細節，缺少跨模組消費穩定規範。 |
| `.npz` 內部陣列名（`schema_version`、`source`、`x_domain`...） | 內部儲存層細節，非 manifest 對外合約基準。 |
| 任何隱含 `requires` 與私有 payload 假設 | 可能形成 displaytools/legacy 耦合，超出目前授權邊界。 |

### pending_o1（待 o_1 或 owner 決議）

| 欄位 | 內容 |
|---|---|
| `ContractCard schema finalization` | 是否將欄位升級為 cross-repo 共享 schema。 |
| `evidence hash / provenance chain` | 是否需要新增可追溯 hash 與版本承諾欄位。 |
| `cross-slice integration mapping` | `c_2` 草案到下游 `Core/Display` 的正式消費映射。 |

### 最小可用證據摘要

- 可作為下一輪規劃輸入（已有命令證據）：`schema_version`, `asset_kind`, `compression_family`, `reconstruct_modes`, `error_metrics`, `evidence_outputs`, `compatibility_profile`, `generated_at`, `tool_version`。
- 仍需治理授權前僅供下游規劃參考，不視為正式可消費。

## B. startup / SOP drift scan（本分支）

### 已修正

1. `docs/AGENT_START_HERE.zh-TW.md`
   - 移除啟動必需路徑中的不存在檔案項：`docs/DOCS_INDEX.zh-TW.md`、`docs/DEVELOPMENT_LOG.zh-TW.md`。
2. `docs/DEVELOPMENT_GOVERNANCE.md`
   - 修正「Renderer/runtime interoperability」指向，改為 `docs/benchmarks/*` + Notion review 流，而非已移除的本地 notes 檔。

### 仍需關注

1. `docs/AGENT_HANDOFF.md` 仍保留跨專案整合語句（例如未來回接 `RRKAL Core` / `displaytools`），屬歷史規劃，不應被視為當前已授權行為。
2. `docs/benchmarks` 三文件族仍應在更新時保持命令口徑一致（目前 AGENT handoff 已記錄，但需持續同步）。

### startup drift 決策結果

- `docs/AGENT_START_HERE.zh-TW.md` 目前不再以不存在文件作為啟動 gate。
- `DEVELOPMENT_GOVERNANCE.md` 不再引用已刪除的 notes 檔作為唯一 interoperability 來源。
- 無需新增整合實作或調整產品流程。

## C. 下一步分層建議

1. `c_2` 將本表作為 `c_1 / c_3` 的「規劃輸入證據清單」
2. 將 `unsafe` 欄位保留在草案層，避免下游當作 parser 必需欄位。
3. 僅在 `pending_o1` 全部決議後，才提交 ContractCard schema 地址化（非本次 docs-only scope）。
