# ContractCard schema-change impact gate（草案）

- 目標：規範 `ContractCard` 欄位提升到「可進入下游規劃使用」前，必須通過的變更影響盤點與否決門檻。
- 參照：`docs/CONTRACTCARD_REFERENCE_CONSUMER_BOUNDARY_ADR_DRAFT.zh-TW.md`（commit `f092e7b`）。
- 範圍：docs-only / evidence-contract-only / L2。
- 邊界：不得改 manifest schema、CLI 行為、`.vizasset` 套件行為；不得宣告 Core / Display / Odoriba 可作為下游即時實作依據。

## 1) 欄位分類（影響層級）

### safe planning input（僅規劃輸入）

這些欄位可作為內部規劃輸入參考，不需要 schema/CLI 變更。

- `schema_version`
- `asset_kind`
- `compression_family`
- `reconstruct_modes`
- `error_metrics`
- `evidence_outputs`
- `compatibility_profile`
- `generated_at`
- `tool_version`

### schema-change required（若要作為正式可消費下游欄位）

這些欄位需要改 manifest schema 或已存輸出格式，並要有對應驗證策略。

- `contract_id`：需加入穩定主鍵欄位
- `payload_shape`：需定義 `dim/channels/dtype` 形式
- `source_manifest_hash`：需新增可核對 hash
- `benchmark_profile`：需明確化 benchmark 能力欄位與欄位型別
- `consumer_hints`：需有可解析版本化 schema

### downstream agreement required（需 o_1 / owner / c1-c4 共識）

在 schema 確認前，這些欄位不列入正式共享承諾。

- `compatibility_profile.requires`
- `preview_contract`（例如 preview 支援邏輯的外部解讀）
- `evidence_outputs` 的正式 `Artifact contract` 命名與版本
- `reconstruct_modes` 與 reconstruction payload 版本對齊

### unsafe（不得直接放入下游可消費欄位）

- `model.primary_method` 原生字串（未版本化）
- `model.methods` 內部實作列表
- `.npz` 內部欄位名（非對外契約）
- `compatibility.requires` 中含有未授權下游耦合意圖的條件

## 2) 升級影響總表

| 欄位 | 推升到正式可消費結果 | 主要觸發點 | 是否需 schema 變更 | 是否需 downstream agreement |
|---|---|---|---|---|
| `schema_version` | 可作為版本驗證基底 | manifest 驗證一致性 | 無（維持現況） | 無 |
| `asset_kind` | 下游可依資產類型做判讀 | manifest 輸出對齊 | 無（維持現況） | 無 |
| `contract_id` | 形成跨系統唯一標識 | manifest + review 契約鏈 | 是 | 是 |
| `payload_shape` | 下游可預先驗證載荷可用性 | manifest schema / compatibility | 是 | 是 |
| `source_manifest_hash` | 可稽核 provenance 鏈 | manifest + artifact | 是 | 是 |
| `consumer_hints` | 下游行為提示可被 parser 消費 | schema 定義 | 是 | 是 |
| `benchmark_profile` | downstream 可做資源與風險估算 | benchmark 報告欄位對齊 | 可能是 | 是 |
| `compatibility_profile.requires` | 下游依賴宣告可被授權解析 | schema + 文件邏輯 | 是 | 是 |
| `reconstruct_modes` | 支援介面合約明確化 | CLI / compatibility | 視情況 | 是 |

## 3) Negative consumer gate（負向消費門檻）

目標：防止欄位在未完成準備時被下游誤用。

### Gate input

- 當前欄位分類（safe / schema-change / downstream / unsafe）
- `manifest schema` 是否含穩定主鍵與版本
- 是否有對應 pytest 契約證據（測試名單）
- 是否已更新 `.vizasset` 產出文件（manifest / review / artifacts）

### Gate rules

1. `classified as safe planning input`：
   - 允許留在 `c_2` 規劃文件與 ADR 中。
   - 禁止宣告為 `ContractCard` 下游正式可用字段。
2. `classified as schema-change required`：
   - 未經 schema 調整不得進入任何下游消費文檔。
   - 若提案升級，必須完成 schema、版本、測試與文件更新後才可標示為 candidate。
3. `classified as downstream agreement required`：
   - 未完成 o_1 / owner / c1-c4 協議前，固定停在 draft。
   - 所有對外文件需加 `pending_o1` 標記。
4. `classified as unsafe`：
   - 一律不加入下游 `ContractCard` 參考/消費列表。
   - 必須保留 internal-only 標註並追蹤在 `pending_o1`。

### Gate fail actions

- 若任一 `schema-change required` 欄位未完成 schema 釋出：
  - 不能放入下游可消費候選。
  - 需保留於 ADR/taxonomy 規劃層。
- 若任一 `downstream agreement required` 欄位未完成授權：
  - 不能產生 acceptance wording。
  - 只能在文件中註明 `pending_o1`。
- 若 unsafe 欄位被引用為 parser 必需欄位：
  - 需立即回退、回歸到規劃輸入層。

### Gate evidence（建議）

- `tests/test_cli_smoke.py`
- `tests/test_precheck_benchmarks.py`
- `tests/test_timeseries_compression.py`
- `tests/test_video_benchmarks.py`

## 4) 對外文檔措辭規則

- 一律使用：`planning input`, `draft`, `pending_o1`，避免未授權 adoption / 就緒性表述。
- 不使用未授權之對外消費結論措辭。
- 所有欄位變更討論都標明 `schema-change required` 或 `downstream agreement required`。

## 5) 結論

目前可接受的安全邊界是：
- 允許 `safe planning input` 在 `.vizasset` 專案內作為規劃參考；
- 任何 `schema-change required` 與 `downstream agreement required` 欄位，除非通過 gate，否則不得出現在下游可消費承諾；
- `unsafe` 欄位只保留內部治理。