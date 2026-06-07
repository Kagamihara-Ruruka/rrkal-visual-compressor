# Compression Contract Next Slice Planning Packet（c_2）

## Packet ID
- `c2_compression_contract_next_slice_planning_packet`

## Objective
- 在維持 docs/evidence-only 邊界下，為下一個 `c_2` docs/surface 工作切片定義最小、可交接、非整合的下一步。

## Scope lock (hard boundaries)
- 保持 docs-only；不改：
  - `.vizasset` manifest / schema
  - CLI 行為
  - 壓縮演算法
  - runtime ContractCard / EvidencePacket 實作
  - 跨 repo consumer 實作路徑
- 僅撰寫規劃、索引、邏輯界定與驗證清單。

## Current evidence baseline
- 已存在且可追溯的長掃描：`docs/COMPRESSION_CONTRACT_SURFACE_LONG_SCAN.zh-TW.md`
- 相關契約草案：
  - `docs/COMPRESSION_CONTRACT_SPEC_DRAFT.zh-TW.md`
  - `docs/COMPRESSION_CONTRACT_EVIDENCE_PACKET_DRAFT.zh-TW.md`
  - `docs/COMPRESSION_CONTRACT_EVIDENCE_TAXONOMY_AND_SOP_DRIFT_AUDIT.zh-TW.md`
- ContractCard 相關：
  - `docs/CONTRACTCARD_REFERENCE_CONSUMER_BOUNDARY_ADR_DRAFT.zh-TW.md`
  - `docs/CONTRACTCARD_SCHEMA_CHANGE_IMPACT_GATE.zh-TW.md`
  - `docs/CONTRACTCARD_NEGATIVE_CONSUMER_FIXTURE_MATRIX.zh-TW.md`
- Docs readability：
  - `docs/DOCS_READABILITY_CHECKPOINT_CONTRACT.md`
  - `docs/DOCS_READABILITY_CHECKPOINT_FAILURE_MODES.md`
  - `scripts/docs_readability_checkpoint.py`
  - `scripts/validate_docs_readability_checkpoint.py`
  - `tests/test_docs_readability_checker.py`

## Next bounded slice recommendation (Top 1)
### Slice 1：ContractCard 可消費邊界合併索引（planning input only）
- 目標：
  - 將現有 verified / declared-only / unsafe / pending 分層的欄位結論，濃縮為「planning input」入口索引。
  - 明確列出 `planning-facing` 與 `blocked-for-consumption` 邏輯分區，保證文檔不承諾 parser 強制欄位。
- 為何可安全啟動：
  - 已有足夠證據基底；本 slice 僅整理語義，不觸碰源碼。
- 必要驗證：
  - `git diff --check`
  - UTF-8/U+FFFD/PUA/mojibake/human spot check
  - `python scripts/check_docs_readability.py <target docs>`
- 禁止事項（Slice 內）:
  - `integration-ready`、`production-ready`
  - `已可直接消費`、`可直接 parser` 的字眼
  - 任何跨 repo consumer 承諾語句
  - 任何 manifest/CLI/algorithm/演算法變更

### Slice 2（blocked until Gate 1 可通過）：Negative fixture governance freeze（文件化）
- 目標：
  - 將負向 fixture（safe / schema-change / downstream / unsafe）與實際對應清單固化為「不形成直接承諾」規則。
- 風險：若混入下游承諾句式，將誤導整合節奏。
- Gate：需先完成 Slice 1 的詞彙/邊界校對。

### Slice 3（blocked）：validator posture hardening（docs-only）
- 目標：
  - 形成「checkpoint output schema + boundary flag」的最小更新文件，不改 runner 邏輯。
- 風險：與 meta 測試鏈若無邊界宣告可能復現遞迴 fan-out。
- Gate：需先完成 Slice 1 內 false-readiness 清理與術語對齊。

## Gate decisions to keep this slice bounded
1. 只做 documentation 內容更新。
2. 不建立任何 runtime class / parser / writer。
3. 不新增 `c_2` 之外的可消費規格承諾。
4. 不新增跨 repo integration 路徑。

## O_1 handoff payload checklist
- Selected next slice：`c2_contractcard_field_availability_index_merge_draft`
- Why now：已有證據面完整、只需文件合流。
- What remains unsafe：
  - `model.primary_method`、`model.methods`、`compatibility.requires`（未授權 downstream schema 鎖定前）
- What must be explicit in next packet：
  - `pending_o1` 標註
  - `declared-only` / `unsafe` 區隔
  - `no manifest/schema change` 邊界

## Completion checks required for this packet
- `python scripts/docs_readability_checkpoint.py --json`
- `python scripts/validate_docs_readability_checkpoint.py --self-test-negative`
- `python -m pytest tests/test_docs_readability_checker.py -q`
- `python -m vizcompress --help`
- `python -m vizcompress.cli --help`
- `python scripts/check_docs_readability.py docs/COMPRESSION_CONTRACT_SURFACE_LONG_SCAN.zh-TW.md docs/C2_QUICK_STARTUP_DELIVERY_SOP.md`
- `git diff --check`
- false-readiness wording scan (no integration-ready / direct consumption assertion)

## Boundary statement

Docs/evidence-only next-slice planning packet. No `.vizasset` manifest/schema change, no CLI behavior change, no compression algorithm change, no runtime ContractCard/EvidencePacket implementation, no downstream consumer path, no cross-repo integration, no readiness claim.

## Final classification

`c2_compression_contract_next_slice_planning_packet_ready_for_o1_review`
