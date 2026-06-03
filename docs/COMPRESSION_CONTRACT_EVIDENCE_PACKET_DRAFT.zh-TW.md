# Compression Contract Evidence Packet 草案（未來可驗證）

本文件為 `docs/evidence-contract-only` 草案。目標是將 `CompressionContractSpec` 的能力宣告轉化為可被驗證的 evidence packet / compatibility checklist，供未來協作決策。**不做壓縮演算法實作、不改 schema、不做 integration。**

## TL;DR

- 本文件定義「Compression Contract Evidence Packet（CCEP）」：一組可被 `verify / inspect / reconstruct / benchmark` 對應驗證的欄位與檢核清單。
- packet 不直接做功能承諾，而是宣告「可被誰驗證、驗證了什麼、失敗代表什麼風險」。
- packet 與 `.vizasset` 是綁定關係：以 manifest 為主體、以命令行為為證據來源。
- 未授權：
  - 跨 repo import implementation
  - `displaytools` / `RRKAL_displaytools` 實作整合
  - `RRKAL Core` 功能整合
  - `SkinAsset / RendererSkinAsset` 實作路徑

## What a compression contract evidence packet should prove

- `.vizasset` 可被識別且 manifest 完整（檔案與欄位可被 `verify` 解析）。
- 重建能力被明確陳述，並可在 `reconstruct` 下重現對應模式輸出。
- 品質條件可被重複解讀（metrics 與門檻來源可追溯）。
- 評測可比對性可被證明（bench/precheck 有可追蹤輸出，不宣稱未證實跨環境公平）。
- 兼容性資訊可被外部消費方用於「是否可嘗試消費」的初步決策。

## Relationship to `.vizasset`

- `.vizasset` 是 packet 的承載資產。  
- packet 對應的 `asset.json`（或與其同源之 manifest）必須提供：
  - schema/compatibility 基本欄位
  - model/profile 相關約束
  - metrics/evidence 的生產指紋
- packet 的目的不是替代 `.vizasset`，而是對其可消費性提供「可驗證摘要」。

## Relationship to `verify / inspect / reconstruct / benchmark`

- `verify`: first-pass gate，驗證 manifest 可讀性、欄位完整性、檔案引用一致性。  
- `inspect`: 提供可讀證據與中介觀察（重建預覽上下文、異常來源、樣本摘要）。  
- `reconstruct`: 驗證 `reconstruct_modes` 的實際可執行性與回輸行為。  
- `benchmark` / `precheck-benchmarks`: 驗證 `benchmark_profile` 的資料來源與結果輸出完整性，避免不具比較前提的過度宣告。  

## Compatibility checklist

### Candidate fields（可驗證欄位）

| Field | Meaning | Producer | Consumer | Required now? | Risk |
|---|---|---|---|---|---|
| `contract_id` | 契約版本化識別子，含資產類型與版本語意 | visual-compressor | Core / Display（未來）/ c_1 / c_3 | Y | 缺少唯一性會造成識別混亂 |
| `schema_version` | manifest schema 版本，對齊驗證規則 | visual-compressor | verify / inspect / o_1 | Y | schema 漂移導致解析失敗 |
| `asset_kind` | 資料類型分類（timeseries / video / image / generic） | visual-compressor | verify / reconstruct / benchmark | Y | 模型能力被誤引用 |
| `compression_family` | 壓縮家族（如 spatial_fourier） | visual-compressor | benchmark / roadmap / core-planning | Y | 家族誤標影響比較與資源預估 |
| `payload_shape` | payload 幾何與通道前提 | visual-compressor | reconstruct / inspect | Y | 形狀不明確導致重建失敗 |
| `reconstruct_modes` | 可重建模式（full/signal-only 等） | visual-compressor | reconstruct / verify / core-planning | Y | 模式與參數錯配導致結果偏差 |
| `error_metrics` | 已支援或已報告之品質指標 | visual-compressor | verify / benchmark / o_1 | Y | 指標不一致導致品質誤讀 |
| `benchmark_profile` | benchmark 類型、範圍與輸出可比性 | benchmark command | benchmark / core-planning | Y | 過度宣告比較能力 |
| `evidence_outputs` | metrics/review/scan/report 等輸出清單 | visual-compressor pipeline | verify / inspect / CI / o_1 | Y | 輸出缺失導致自動化無證據 |
| `compatibility_profile` | preview/reconstruct/renderer/native 等限制 | visual-compressor | future parser / consumer planner | Y | 過早假設造成整合阻斷 |
| `consumer_hints` | 未來消費端建議使用邏輯 | visual-compressor | Core / Display（未來） | Y | 沒有治理邊界造成誤消費 |
| `source_manifest_hash` | 源 manifest hash 或等價 hash 指紋 | visual-compressor | verify / audit / CI | N | 缺失會降低溯源性 |
| `generated_at` | packet 生成時間 | visual-compressor | all consumers（審核 / CI） | Y | 無時間戳難以追蹤新舊 |
| `tool_version` | 工具/CLI 版本 | visual-compressor | debug / audit | Y | 版本差異未被記錄難以重現 |

### Compatibility checklist items

| Check | Why it matters | Failure meaning | Future consumer |
|---|---|---|---|
| schema version compatibility | 保證 verifier 能解析且欄位語義一致 | verify 退場，inspect/reconstruct 不能保證成立 | Core / Display |
| reconstruct mode compatibility | 不同重建模式是否都被聲明並可重建 | 模式可選但不可執行，導致能力虛標 | reconstruct / inspect / future clients |
| error metric availability | 確認報告含實際支持的指標 | benchmark 口徑錯位、資料誤判 | benchmark / QA |
| preview support | preview 是否有對應能力與輸出 | 視覺化流程無法做最小驗證 | Display / QA |
| benchmark evidence availability | bench/precheck 是否有完整可追溯輸出 | 比較結論不可重現、CI 無法穩定 | CI / roadmap planning |
| edge/low-compute support | 明確標記是否支援低算力場景 | 部署決策偏差，資源規劃不準 | core-planning |
| generated artifact exclusion | 減少臨時產物污染，保留可再現性 | artifact 污染導致取證成本上升 | CI / audit |
| private payload assumptions | 避免僅依賴私有 `.npz` 欄位假設 | parser 綁死，導致跨版本/跨工具斷裂 | future shared consumer |
| no displaytools overfit | 保持可移植性，不與單一展示工具綁死 | display 端實作過度耦合 | Core / Display（未來） |

## What Core may consume later

1. 可重建可用性（重建模式、schema 兼容與 preview/reconstruct 限制）。  
2. 錯誤指標與評測輸出摘要，用於資源規劃和品質門檻決策。  
3. `source_manifest_hash` 與 `tool_version` 作為追蹤與可重現性欄位。  
4. `consumer_hints` 作為初版消費指引，但不作為實作授權文件。

## What Display may consume later

1. 是否具備 preview 能力與支援格式。  
2. `reconstruct_modes` 在展示場景是否可轉譯（僅概念層，不做 displaytools 實作）。  
3. `compatibility_profile` 與 `error_metrics` 作為降級策略參考。  
4. `evidence_outputs` 中 preview/metrics 相關項目是否齊備，用於展示診斷面板。

## What remains owned by visual-compressor

- `contract evidence packet` 的欄位語義與治理邊界定義。  
- manifest 可驗證欄位與 verify/inspect/reconstruct 的行為邊界。  
- benchmark/scan 合規檢查命名與輸出規格。  
- 產品證據（commits / tests / smoke / CLI output）與文檔證據（packet / checklist）一致性維護。  

## What is not authorized yet

- 以此 packet 作為 `Core` / `Display` 之即時實作輸入；僅為未來設計依據。  
- 將 `RendererSkinAsset / SkinAsset` 列為已授權整合路徑。  
- 修改 `.vizasset` schema、演算法參數、benchmark 門檻。  
- 跨 repo 實作交付。  
- 以此文件取代既有 code-level 測試流程。  

## Risk section

| Risk | Why it matters | Mitigation |
|---|---|---|
| schema drift | 欄位/規則差異導致 verify 無法穩定解析 | 在 packet 與 `.vizasset` 中明確 `schema_version`，並保留 docs drift 檢查 |
| benchmark overclaim | 未聲明實驗條件時仍做跨版本/跨環境可比宣稱 | `benchmark_profile` 必含條件、輸入與輸出範圍 |
| error metrics misunderstood | 指標命名與門檻混淆、解讀歧義 | 欄位 `error_metrics` 與命令輸出一一對應 |
| Core consuming display-only hints | Core 將展示導向訊息誤當實作需求 | 在文件標註「消費建議」與「權責邊界」，不承諾實作 |
| Display consuming governance-only fields | Display 端誤以治理文件為硬性整合條件 | 設計 `consumer_hints` 為「資訊」非「契約必備」 |
| premature .npz assumptions | 對私有 payload 結構過度依賴，失去可替代性 | 將 `payload_shape + compatibility_profile` 作為核心判定欄位，避免硬編碼模型欄位 |
| cross-repo import temptation | 在未授權前引入跨 repo 導入邏輯 | 文件保留「evidence-contract-only」限制，待 o_1 與 owner 決議後再進入 integration slice |

## Optional appendix: CapabilityCode timing

建議 `CompressionCapabilityCode`（例如 `cc.vizasset.timeseries.full-v2`）暫緩啟用，需先滿足：

1. 至少存在 **2 種壓縮家族**（例如 `spatial_fourier` 與另一個可實現家族）；
2. 至少存在 **2 個未來消費者** 有明確對接節點（例如 Core + Display/preview workflow）；
3. 主要能力維度在 packet / 實際證據中的對齊穩定度達到持續一致；
4. packet 中 `compatibility_profile` / `reconstruct_modes` / `benchmark_profile` 不再頻繁重述。  

當上述條件齊備，才轉入能力碼版本治理與分配。  
