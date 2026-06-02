# Agent Start Here（c_1 對齊版）

## 會話啟動（每次新輪作業前）

- Workspace/權限確認  
  - 開始前先視為可寫工作區：`L:\rrkal-visual-compressor`  
  - K: 及其他跨專案 L: 僅參考，原則上只讀
- Repo 快檢  
  - `git status --short --branch`  
  - `git log -1 --oneline --decorate`
- 權威文件最短路徑  
- `docs/AGENT_HANDOFF.zh-TW.md`
- `docs/DEVELOPMENT_GOVERNANCE.zh-TW.md`（若存在）
- `docs/ROADMAP.md`（若存在）
- `docs/ROADMAP.zh-TW.md`（若存在）
- `docs/DOCS_INDEX.zh-TW.md`（若存在，僅作為快速導覽；不作為啟動必需）
- `docs/DEVELOPMENT_LOG.zh-TW.md`（若存在，僅作為歷史歸檔；不作為啟動必需）
- Notion 為主要協調儀表板（非產品證據來源）
- `Agents討論區`（Agents）
  - `04_Agent_Inbox`
  - `03_OAI_Review_Requests`
  - `02_Decision_Log`
  - `06_n1_SOP`
  - GitHub commits / tests / smoke / CLI report / git diff 才是產品證據

## 切片執行規則

- 預設主線建議：`seed -> crawler -> candidate -> plan -> download -> import -> UI`
- 每次只做 bounded slice，避免同時改 crawler / UI / docs / import / 資料夾搬遷
- 每個切片在起手先寫清：
  - 本次要改哪些檔案（含預計觸及）
  - 不碰哪些檔案
  - 預期驗證方式（commands）

## 交付前最小驗證

- 對有變更程式碼：
  - `git diff --check`
  - `pytest` 相關 focused tests（能跑就跑）
  - 能執行 smoke 時，補跑對應 smoke
- 對 `.md` / `zh-TW` / skill 類變更：
  - 做文字編碼與格式一致性檢查（避免 mojibake）
- 文檔治理  
  - 做 docs drift check：更改主張是否已同步到治理/交接文件

## 結束條件（checkpoint）

- commit 保持小且清楚
- push 後需看 GitHub Actions；CI 綠才算穩定 checkpoint
  - Notion 為主要協調儀表板（非產品證據來源）
  - `Agents討論區`（Agents）
    - `04_Agent_Inbox`
    - `03_OAI_Review_Requests`
    - `02_Decision_Log`
    - `06_n1_SOP`
  - GitHub commits / tests / smoke / CLI report / git diff 才是產品證據

