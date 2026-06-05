# ADR: ContractCard 參考邊界草案（c_2）

## TL;DR

- `ContractCard` 在本 repo 內，僅作為 `RRKAL visual-compressor` 的 **規劃輸入證據**。
- `.vizasset` 目前可證明欄位與輸出，仍不等於供下游規劃與規格草擬使用，不代表正式對外 schema。
- `Core / Display / Odoriba` 的實際消費 schema 需經 `o_1` + owner 再議。

## Scope

本 ADR 僅定義「目前可參照」與「不可直接落庫使用」的邊界，保持 `L2` docs-only。

- 目標 repo：`L:\rrkal-visual-compressor`
- 影響範圍：`ContractCard` 欄位對齊與下游可消費判斷邏輯
- 禁止變更：
  - manifest schema
  - CLI 行為
  - `.vizasset` 套件行為
  - 跨 repo integration

## 現況依據（manifest / CLI / tests）

- manifest 形狀與驗證：`src/vizcompress/packages.py`
- 命令輸出與行為：`src/vizcompress/cli.py`
- 預熱證據（tests）：`tests/test_cli_smoke.py`、`tests/test_precheck_benchmarks.py`、`tests/test_timeseries_compression.py`、`tests/test_video_benchmarks.py`

## A. verified（manifest/CLI/test-backed）

| 欄位 | 來源 | 現況 | 為何可用 |
|---|---|---|---|
| `schema_version` | manifest (`asset.json`) / `validate_vizasset` | verified | `packages.py` 目前強制 `ASSET_SCHEMA_VERSION`，並有測試覆蓋。
| `asset_kind` | manifest + inspect 輸出 | verified | 對應現行 `asset_type`，可在回報中重建。
| `compression_family` | manifest (`model.primary_method`) | verified | 目前有一致的壓縮方法輸出。
| `reconstruct_modes` | compatibility + reconstruct 行為 | verified | `compatibility` 與 reconstruct/inspect 行為一致。
| `error_metrics` | metrics block + CLI output | verified | `verify`/`inspect` 可輸出可比對指標。
| `evidence_outputs` | `files`、`metrics.json`、`review.json` | verified | 多命令可產生可追蹤輸出。
| `compatibility_profile` | manifest compatibility block | verified | 含 reconstruct / preview 等可互參值。
| `generated_at` | `generated_at_utc` | verified | manifest/review 流都有時間戳。
| `tool_version` | generated metadata | verified | 具版本來源欄位。

## B. declared-only（尚未可下游消費）

| 欄位 | 來源 | 限制 |
|---|---|---|
| `contract_id` | 草案建議 | 僅 draft，未定義穩定發佈主鍵與生命週期。
| `consumer_hints` | 規格/備忘文本 | 僅治理建議，非 parser 強制欄位。
| `payload_shape` | source + model 資訊 | 缺少跨壓縮族正規化版本。
| `benchmark_profile` | benchmark/precheck 輸出建議 | 尚未綁進正式 ContractCard schema。
| `source_manifest_hash` | 計畫字段 | 尚未完整可核對鏈路。

## C. unsafe downstream fields（不建議直接引用）

- `model.primary_method` 原生字串值
- `model.methods` 原始清單
- `.npz` 內部欄位名
- `compatibility.requires` 中含有跨 repo 的實作暗示

## D. pending_o1 fields（需 o_1 / owner）

- `contract_id` 穩定化規範與命名空間
- `evidence hash / provenance` 欄位與可驗證鏈路
- `consumer_hints` 的正式上下游對齊版本
- `preview / reconstruct` 跨 repo 交付格式

## E. fields requiring manifest schema change（不在本次 scope）

- 將 `contract_id` 壓為穩定主鍵欄位
- 新增 `evidence_trace`（含 hash、input/output binding）
- 新增 schema 內生版控欄位（若要跨 repo 自動消費）
- 將 `payload_shape` 常態化（`dim / channels / dtype`）

## F. fields requiring c1/c3/c4 agreement（不在本次 scope）

- 將 `compatibility_profile.requires` 擴充為下游互通約束
- 任何 `ConsumerCard` / `AssetCard` 的正式欄位凍結
- `preview` 與 `reconstruct` 的 cross-slice 契約語義
- `AssetCard` 最小可消費集合正式定稿

## Minimal reference candidate（draft, non-schema, pending_o1）

```yaml
contract_card_reference:
  contract_id: draft:vizcompress:timeseries:reconstructable:0.2
  schema_version: "0.2"
  asset_kind: timeseries
  compression_family: spatial_fourier
  reconstruct_modes: [full, signal-only]
  error_metrics: [rmse, mae, max-error]
  compatibility_profile: {reconstructable: true, preview: svg}
  evidence_outputs: [metrics.json, review.json]
  consumer_hints: pending_o1
  generated_at: "<manifest.generated_at_utc>"
  tool_version: "<generated_by.version>"
```

## Branch scan summary

- verified: 9
- declared-only: 5
- unsafe: 4
- pending_o1: 4
- needs_schema_change: 4
- needs_c_team_agreement: 4

## Boundary statement

- 這是 docs-only 的「規劃輸入證據」定義。
- 不建立下游正式消費承諾。
- 不修改 schema / CLI / 套件行為。
- 不授權跨 repo implementation。

## Forbidden wording checks (this ADR)

- 禁止將 `ContractCard` 描述為「已可直接生產消費」。
- 禁止將任何規劃字段宣告為 `Core / Display / Odoriba` 即時可用。