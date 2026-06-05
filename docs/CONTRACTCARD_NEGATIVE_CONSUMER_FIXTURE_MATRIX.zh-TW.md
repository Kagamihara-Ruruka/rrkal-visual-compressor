# ContractCard 負向消費 Fixture Matrix（草案）

- 來源參照：
  - `docs/CONTRACTCARD_REFERENCE_CONSUMER_BOUNDARY_ADR_DRAFT.zh-TW.md`
  - `docs/CONTRACTCARD_SCHEMA_CHANGE_IMPACT_GATE.zh-TW.md`
  - `docs/COMPRESSION_CONTRACT_EVIDENCE_TAXONOMY_AND_SOP_DRIFT_AUDIT.zh-TW.md`
- 參考承載：`f092e7b`
- 目的：把欄位分級轉為「不能被下游直接採納」的負向測試矩陣，作為規劃與審核入口。
- 模式：docs-only（不實作 schema / CLI / .vizasset / integration）

## 0. 口徑一致

- 本文件只做 evidence 級別的規範，不構成對外直接可用契約。
- 所有欄位只用四分類追蹤：
  1. `safe planning input`
  2. `schema-change required`
  3. `downstream agreement required`
  4. `unsafe`
- 「negative fixture」定義：
  - 該 fixture 用來保證欄位不會被當成下游可解析主欄位。
  - 不驗證功能邏輯，只驗證文件與承諾邊界。

## 1. Negative fixture matrix（欄位 -> 不可下游採納條件）

### A. safe planning input（可保留為規劃證據）

| 欄位 | 應該阻擋的下游行為 | 負向 fixture 名稱 | 目的 |
|---|---|---|---|
| `schema_version` | 不得被標成穩定對外 schema 的單點決策 | `fixture_safe_schema_version_not_final_contract` | 驗證仍需依賴外部協議進入下一階段 |
| `asset_kind` | 不得作為 parser 強制欄位 | `fixture_safe_asset_kind_no_parser_contract` | 僅作為規劃輸入證據 |
| `compression_family` | 不得直接做跨團隊強耦合分派 | `fixture_safe_compression_family_not_routing_source_of_truth` | 限定在本 repo 流程 |
| `reconstruct_modes` | 不得直接對外聲明為完整重建保證 | `fixture_safe_reconstruct_modes_not_guaranteed` | 確保需另行版本與效能條款 |
| `error_metrics` | 不得被下游當成評估唯一標準 | `fixture_safe_error_metrics_not_single_sla` | 只保留證據欄位 |
| `evidence_outputs` | 不得宣告為跨系統唯一輸出清單 | `fixture_safe_evidence_outputs_not_contract_surface` | 僅作為審核輸出之一 |
| `compatibility_profile` | 不得將 `renderability` 視為正式可交付保證 | `fixture_safe_compatibility_profile_no_contract_contract` | 保留規劃用途 |
| `generated_at` | 不得作為不可變的時序承諾 | `fixture_safe_generated_at_not_immutable_timestamp` | 僅作為追溯欄位 |
| `tool_version` | 不得直接定義跨團隊行為門檻 | `fixture_safe_tool_version_not_runtime_gate` | 只保留追溯用途 |

### B. schema-change required（尚未到可採納門檻）

| 欄位 | 現況阻斷條件 | 負向 fixture 名稱 | 後續才可放行 |
|---|---|---|---|
| `contract_id` | 缺 stable key、生命週期規則 | `fixture_needs_contract_id_schema_maturity` | manifest schema 擴充、命名規則、版本策略 |
| `payload_shape` | 缺 `dim / channels / dtype` 一致規格 | `fixture_needs_payload_shape_normalization` | 跨族欄位規範完成 |
| `source_manifest_hash` | 缺 hash 鏈與 binding 證據 | `fixture_needs_source_manifest_hash_evidence` | provenance 欄位與校驗機制補齊 |
| `benchmark_profile` | 未明確 profile 型別與準則 | `fixture_needs_benchmark_profile_contract` | benchmark profile schema 完成 |
| `consumer_hints` | 缺 parser 可解析版本化欄位 | `fixture_needs_consumer_hints_versioned` | versioned hint contract 建立 |

### C. downstream agreement required（需 o1/owner/c1-c4 同意）

| 欄位 | 現況阻斷條件 | 負向 fixture 名稱 | 需要通過的治理 |
|---|---|---|---|
| `compatibility_profile.requires` | 跨團隊依賴解讀未對齊 | `fixture_requires_requiring_downstream_alignment` | o_1 / owner / c1-c4 共識 |
| `preview_contract`（或 preview 解讀欄位族） | preview 解讀邏輯未正式授權 | `fixture_preview_contract_not_cross_repo_ready` | 需預覽責任範圍與錯誤策略確認 |
| `evidence_outputs`（artifact 命名） | 命名版本未對齊 | `fixture_artifact_contract_naming_pending` | Artifact 命名與版本政策定稿 |
| `reconstruct_modes`（payload version） | payload 版本與行為契約未鎖定 | `fixture_reconstruct_modes_version_pending` | 外部契約版本矩陣確認 |

### D. unsafe（不能進入下游參考主清單）

| 欄位 | 阻斷理由 | 負向 fixture 名稱 | 要求 |
|---|---|---|---|
| `model.primary_method` | 實作字串值未版本化 | `fixture_unsafe_model_primary_method_internal_only` | 僅保留內部診斷用途 |
| `model.methods` | 詳細列表偏實作細節 | `fixture_unsafe_model_methods_not_contract` | 未來視需求重構為中立方法碼 |
| `.npz` 內部欄位名 | 內部儲存結構非對外 | `fixture_unsafe_npz_internal_fields_private` | 禁止文件宣告對外必需 |
| `compatibility.requires`（未授權耦合） | 含跨 repo 實作耦合暗示 | `fixture_unsafe_internal_requires_not_downstream` | 等待治理後再轉為 declared-only |

## 2. Negative consumer gate（表述）

- 只要某欄位仍在 B / C / D 分類中，且未完成對應升級步驟，就不應出現在下游 parser/導入文檔的 required 清單。
- 若出現：
  1. 缺失欄位聲明（例如 schema 欄位未落地）
  2. 缺少 `pending_o1` 或等級註解
3. 語義與產出不一致

  以上任一成立，該 fixture 視為 fail，需退回 `safe planning` / `pending` 分層。

## 3. 需要補齊的 fixture shape（未實作）

### 未實作但建議保留的 fixture 列表

- `fixture_safe_*`：覆蓋 safe planning 欄位在文件層級仍不得上升為下游承諾
- `fixture_needs_*`：檢核 schema/治理缺口是否補齊
- `fixture_requires_*`：檢核是否有跨團隊一致決議
- `fixture_unsafe_*`：防止 internal 欄位誤進下游 required 表

### 未來 test 名稱建議（docs-only 記錄）

- `test_contractcard_negative_fixture_matrix_has_no_downstream_contract_writes`
- `test_contractcard_fields_blocked_without_gate`
- `test_contractcard_matrix_includes_unsafe_fields`
- `test_contractcard_pending_fields_marked_pending_o1`

## 4. 失敗條件（否決清單）

- 若 `unsafe` 欄位被列入下游 parsing 必要欄位
- 若 `schema-change required` 欄位未更新 schema 即被當作對外可用欄位（本文件避免就緒性措辭）
- 若 `downstream agreement required` 欄位未有 `pending_o1`/授權標註即出現對外承諾
- 若 future test 名稱與 fixture shape 無法對應目前分級

## 5. 邊界聲明

- 不改 manifest schema。
- 不改 CLI 行為。
- 不改 `.vizasset` 套件行為。
- 不宣告 Core / Display / Odoriba 可即時使用。
- 不做 c_1 / c_3 / c_4 integration 推進。