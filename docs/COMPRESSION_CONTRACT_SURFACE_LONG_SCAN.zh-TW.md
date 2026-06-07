# Compression Contract Surface Long Scan（c_2）

## 1. 盤點範圍與目標

本文件為 `c_2` 在 docs/evidence 限制下的長掃描彙整，聚焦 `.vizasset` 契約面向、ContractCard 對接候選、EvidencePacket 對齊、以及 docs/readability checkpoint 作為交付守門面。

## 2. Phase A Surface Inventory

| surface | current evidence | owner file/doc | machine-readable status | risk level | risk | next possible gate |
| --- | --- | --- | --- | --- | --- | --- |
| CompressionContractSpec | 具備 TL;DR、契約核心定義、能力維度表、pseudo-structure、風險註記；已標註 `docs-only` 邊界 | docs/COMPRESSION_CONTRACT_SPEC_DRAFT.zh-TW.md | `docs-contract-candidate` | 中高（文件主體已齊全） | 文件被誤讀為 schema finalization | 下一步可形成 `Compression Contract Surface index` |
| EvidencePacket | 已有欄位意義表、compatibility checklist、risk、owner/owned-not-authorized 區塊；含 `planning-only` 提示 | docs/COMPRESSION_CONTRACT_EVIDENCE_PACKET_DRAFT.zh-TW.md | `docs-contract-candidate` | 中（欄位尚未形成 parser contract） | 欄位混用時誤當下游消費欄位 | 下一步可做負向/正向欄位 validator 設計草案（僅文件） |
| ContractCard | 多份 doc 形成 verified / declared-only / unsafe / pending_o1 分層（ADR、taxonomy、impact gate、fixture matrix） | docs/CONTRACTCARD_REFERENCE_CONSUMER_BOUNDARY_ADR_DRAFT.zh-TW.md；docs/COMPRESSION_CONTRACT_EVIDENCE_TAXONOMY_AND_SOP_DRIFT_AUDIT.zh-TW.md；docs/CONTRACTCARD_SCHEMA_CHANGE_IMPACT_GATE.zh-TW.md；docs/CONTRACTCARD_NEGATIVE_CONSUMER_FIXTURE_MATRIX.zh-TW.md | `validator-candidate` | 中 | 主要風險為消費語義過早外推 | 下一步可產出最小 reference shape（planning input）與 fixture 對應檢核 |
| .vizasset manifest boundary | manifest 已維持 0.2，`packages.py` 驗證與 `asset.json`/review 共同作為證據面；已明文禁止非授權 schema 變更 | docs/COMPRESSION_CONTRACT_SPEC_DRAFT.zh-TW.md；docs/COMPRESSION_CONTRACT_EVIDENCE_PACKET_DRAFT.zh-TW.md；docs/COMPRESSION_CONTRACT_EVIDENCE_TAXONOMY_AND_SOP_DRIFT_AUDIT.zh-TW.md | `schema_change_blocked` | 高 | 若被改寫會牽動核心行為和交付宣告邊界 | 下一步只可做 docs-only boundary 強化，不進行程式變更 |
| CLI/help boundary | 已定義 canonical 本地入口與 `src/vizcompress` 作為主實作；近期測試也已驗證 entrypoint | docs/C2_QUICK_STARTUP_DELIVERY_SOP.md；scripts/docs_readability 工具鏈 | `cli_help` via helper scripts | 中 | 不能在同一個 slice 修改 CLI | 下一步為 checkpoint / validator 觀察而非 CLI 變更 |
| docs readability checkpoint JSON | 契約文件與腳本雙向對齊：`schema=docs-readability-checkpoint/v1`、required booleans、boundary flags、`c2_python_process_count` | docs/DOCS_READABILITY_CHECKPOINT_CONTRACT.md；scripts/docs_readability_checkpoint.py | `checkpoint_surface` | 中 | 遞迴 fan-out/JSON 非純化/timeout 漏掃描為主要技術風險 | 建議維持 lane-only 驗證，不做功能擴張 |
| docs readability validator | 有 schema + boundary + negative mutation 自我測試；支援 `--self-test-negative`；目前以 meta test 形式存在 | scripts/validate_docs_readability_checkpoint.py；tests/test_docs_readability_checker.py | `validator_candidate` | 中 | validator 對 checkpoint 的呼叫路徑若失控會引發遞迴 fan-out | 維持 meta 觀測、禁止 checkpoint 直接串 meta tests |
| negative fixture behavior | `clean/fffd/pua` fixture 已建立，且在 checker、checkpoint、validator 中可被引用 | tests/fixtures/docs_readability/*.md；tests/test_docs_readability_checker.py | `fixture_matrix_candidate` | 中 | 若語義重用不當，可能變成 readiness claim | 只能保持為負向治理信號，不作 runtime consumer input |
| failure-mode troubleshooting index | 已有失敗模式、升級順序、process fan-out 清單與 timeout 規範 | docs/DOCS_READABILITY_CHECKPOINT_FAILURE_MODES.md | `checkpoint_surface` | 低 | 內容與既有實作描述不一致風險 | 持續同步命令輸出欄位格式 |
| benchmark/review JSON surface | Evidence docs 已引用 `metrics.json`、`review.json`、`scan/bench/contract report`；未定義正式 consumer schema | docs/COMPRESSION_CONTRACT_SPEC_DRAFT.zh-TW.md；docs/COMPRESSION_CONTRACT_EVIDENCE_PACKET_DRAFT.zh-TW.md；docs/COMPRESSION_CONTRACT_EVIDENCE_TAXONOMY_AND_SOP_DRIFT_AUDIT.zh-TW.md | `consumer_boundary_risk` | 中 | 當作下游 contract schema 風險 | 先保留為 planning evidence + pending_o1 |

## 3. Phase B 四路分支掃描

### Branch A: docs-only contract index
- evidence observed: 已有三段 evidence 文件形成完整索引脈絡（spec / evidence packet / mapping)
- risk if chosen: `docs` 被解讀為 `.ContractCard` schema finalization（需在分類欄位上反覆加 `draft / planning / pending_o1`）
- validation available: 文件內文互相對照 + readability guard + false-readiness wording scan
- recommended next action: 先產出本長掃描文檔為入口索引，並明確標註「非正式 consumer schema」
- stop condition: 出現未標註 `pending_o1` 或 `declared-only` 即將欄位視為正式契約
- classification: `docs_contract_candidate`

### Branch B: validator candidate
- evidence observed: checkpoint script + contract schema + validator +負向測試形成一套邊界可驗證集合
- risk if chosen: 元測試/validator 相互呼叫造成遞迴 fan-out 與 process 爆量
- validation available: `python scripts/validate_docs_readability_checkpoint.py --self-test-negative`、`test_meta_*`、`--json` 純 JSON 驗證
- recommended next action: 僅做 topology 保全與文檔收斂，不新增 runtime 路徑
- stop condition: validator/runner 互召回路恢復
- classification: `validator_candidate`

### Branch C: negative fixture matrix
- evidence observed: 已有負向消費 fixture 表與建議 test 名稱，涵蓋 safe/planned/schema-change/unsafe/pending
- risk if chosen: 將 false fixture 轉為 readiness claim 或 consumer assertion
- validation available: `tests/test_docs_readability_checker.py`、negative fixture strict 掃描結果、`--self-test-negative`
- recommended next action: 保持為治理矩陣文件，僅明確標注 `safe planning input` / `pending_o1`
- stop condition: 出現將欄位描述為可直接對外 parser 強制使用或即時整合就緒表述
- classification: `fixture_matrix_candidate`

### Branch D: blocked implementation path
- evidence observed: 所有範圍邊界一致鎖定，且多份文檔明文阻斷 manifest/schema、CLI、algorithm、跨 repo 消費
- risk if chosen: 一旦跨越，會進入未授權 integration path
- validation available: 文件邊界條款 + grep 只允許詞彙
- recommended next action: 維持只讀；不新增 class/writer/consumer path
- stop condition: 需要改 source / schema / CLI / algorithm / cross-repo import
- classification: `algorithm_do_not_touch`

## 4. Phase C 推薦下一步（Top 1-3）

1. **ContractCard field availability index consolidation（本輪推薦）**
   - why safe now: 已有完整 verified / declared-only / unsafe / pending 分層，可直接整合成一頁分類證據
   - why not implementation yet: 不產生任何 parser contract，不改 schema / manifest
   - required validation: docs-only diff check、false-readiness scan、UTF-8/U+FFFD/PUA/mojibake scan
   - forbidden: 避免 `integration-ready`、`immediate-consumption-ready`、`直接作為 parser 必要欄位` 等斷言
   - expected classification: `c2_contractcard_field_index_merge_draft`

2. **Evidence-backed docs-only validator posture review（不改 code）**
   - why safe now: 有現成 script/validator 可補齊 field checklist 與 boundary 言明，且可用 `--self-test-negative` 防退化
   - why not implementation yet: 仍維持 `docs/evidence-only`；不進入任何 runtime class
   - required validation: checkpoint JSON 純淨驗證、negative mutation、pytest leaf/meta 分離
   - forbidden: checkpoint 不得呼叫 meta tests；禁止遞迴 fan-out 或形成 meta 路徑反向呼叫
   - expected classification: `c2_docs_validator_topology_review_complete`

3. **Negative fixture governance freeze（文件化）**
   - why safe now: 目前已有 fixture 結構，下一步只需收斂成「可消費邊界」條款
   - why not implementation yet: 欄位仍未 schema 化
   - required validation: `test_leaf_*` + negative fixture strict 批改規則維持
   - forbidden: 不將 unsafe/pending 欄位寫入下游 parser 必需清單
   - expected classification: `c2_negative_fixture_governance_stable`

## 5. 可讀性 / 遞迴守門檢查

- recursive fan-out guard status: 已由 SOP/contract/failure-index 明文要求
  - checkpoint 僅跑 `test_leaf_*`
  - validator 用於 JSON/policy 驗證且提供 `--self-test-negative`
  - 不允許 checkpoint 直接觸發 meta 測試
- false-readiness scan: 本文件與既有核心文件均以 `planning input / draft / pending_o1` 方式表述，未進入產品整合斷言
- manifest/schema/CLI/algorithm 改動：本輪無

## 6. Stop conditions（若再進一步）

- 若需改 source / schema / manifest / CLI / algorithm：停止此 slice
- 若需新增 runtime class/writer：停止此 slice
- 若需跨 repo 權限消費或承諾 integration：停止此 slice
- 若 checkpoint/validator 出現非純 JSON stdout：停止並回滾
- 若 docs readability 掃描出現新 mojibake / U+FFFD / PUA 上升：停止並進行 tool/payload 修復

## 7. Boundary statement

Docs/evidence-only long scan. No `.vizasset` manifest/schema change, no CLI behavior change, no compression algorithm change, no runtime ContractCard/EvidencePacket implementation, no downstream consumer path, no cross-repo integration, no readiness claim.

## 8. Final classification

`c2_compression_contract_surface_long_scan_ready_for_o1_review`
