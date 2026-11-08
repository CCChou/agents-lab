# 發展方向

> 目標：以練習 agent 技術和架構設計為主，並做出實際有用的 RSS 摘要工具。決策原因見 `docs/decisions.md`。

## 目前能力

- 終端機多輪對話，對話記憶只存在記憶體
- 輸入 `/reset` 開始新對話，舊對話保留但不再送給模型（見 D-034）
- `python -m agent serve` 在本機提供 HTTP API，以 SSE 串流回覆和工具事件（見 D-035）
- 支援任何 OpenAI 相容的 Chat Completions API，可選填 `reasoning_effort`（見 D-023）
- 工具呼叫迴圈
- 用 Miniflux 工具查詢 RSS 文章的標題、feed、category、已讀狀態、發布時間和網址，由新到舊排序
- 依 category 開頭查詢，每個 category 最多 15 篇，可用 `offset` 翻頁，輪流合併，並回報顯示數和總數（見 D-024、D-027）
- 回答一個問題最多看 60 篇標題，先查各 category 的篇數再規劃分配，由 prompt 要求（見 D-032、D-033）
- 模型服務拒絕無效的工具呼叫時，重試一次（見 D-028）
- 看趨勢時預設只讀標題；摘要多篇或推薦時先依標題判斷重要度，一輪最多摘要 5 篇，由程式強制（見 D-025、D-027）
- 回覆使用固定區塊，並列出查詢範圍和查證程度（見 D-025）
- 查詢結果去除同標題文章，category 由關鍵字對照選擇（見 D-029）
- 讀取 Miniflux 保存的內文和公開網頁，摘要單篇和少量文章
- 終端機互動時，回覆以 Markdown 分段渲染，輸入可正確編輯中文；其他情況維持純文字串流（見 D-026）
- 用工具查詢目前時間（見 D-018）

## 已知問題

- [ ] 連續摘要多篇時可能碰到模型服務的每分鐘額度（Groq 上限 7,000 token），目前沒有自己的等待機制
- [ ] `fetch_page` 對部分網站會留下導覽文字，例如中新网
- [ ] 對話本身會無限增長，長對話可能超過模型的 context 上限
- [ ] 對話在程式結束後就消失
- [ ] 摘要多篇時回報的剩餘篇數不一定正確，3 次實測有 1 次用已取得的篇數計算（見 D-024）
- [ ] 摘要 5 篇要 2 到 4 分鐘，原因還沒查
- [ ] 同一個 category 有多個 feed 時，不保證各 feed 平均分到名額，例如中新網（見 D-027）
- [ ] `miniflux_query_entries` 的顯示數假設前面的頁都看過，跳頁時會多算（見 D-029）

## 路線

### 階段 0：穩定基礎（已完成）

- 修正工具呼叫上限的 bug（見 D-014）
- 讓 CLI 能處理 LLM 錯誤，不會中斷對話

### 階段 1：架構拆解（已完成）

練習重點：Clean Architecture、元件邊界。目標元件見 `docs/architecture.md`。

- [x] 把 `Chat` 拆成 `LoopAgent`、`AgentSpec`、`ConversationStore`
- [x] 新增 `Agent`、`AgentRequest`、`Event`、`ContextBuilder`、`ToolRegistry`
- [x] `Message` 改成內容區塊，先只實作 `TextPart`
- [x] 新增 `rss` agent（見 D-017）

### 階段 2：單篇與少量文章摘要（已完成）

練習重點：工具設計、system prompt 設計。

- [x] 文章列表由新到舊排序，`limit` 上限 20（見 D-022）
- [x] 新增 `miniflux_get_entry`，讀取 Miniflux 保存的內文（見 D-019）
- [x] 新增 `fetch_page`，讀取只有摘要的文章（見 D-019）
- [x] 把文章內容視為不可信資料，防範 prompt injection（見 D-021）
- [x] 清除舊的工具結果，限制單次讀取長度（見 D-020）
- [x] 完成「摘要這篇文章」
- [x] 新增 `summarize_entry`，逐篇摘要（見 D-022）
- [x] 完成「摘要今天的未讀文章」，一次最多 5 篇

### 階段 2.5：CLI 和 Web 透過服務對話（進行中）

練習重點：入口 adapter、傳輸邊界、串流。這一階段提前到階段 3 之前，讓 CLI 和 Web 共用同一份 session（見 D-035）。

- [x] 常駐服務和 HTTP API，以 SSE 串流事件
- [x] CLI 改成服務的客戶端：`RemoteAgent`、`RemoteSessions`、`SessionLifecycle`
- [ ] Web：開始前先決定從哪裡打開、要不要驗證，以及前端的做法

### 階段 3：大量文章摘要

練習重點：context 管理、token 計算、map-reduce、workflow。

- 計算 token 用量
- 在 `ContextBuilder` 修剪或壓縮對話本身（舊工具結果的清除見 D-020）
- 實作 `DigestAgent`：先逐篇摘要，再彙整成總覽
- 把趨勢分析做成固定流程的 workflow：查標題、歸納議題、摘要重點、整理報告（見 D-031）
- 「查詢範圍」改由程式統計，處理量分開顯示看過標題和未看過的篇數（見 D-031）

### 階段 4：摘要品質評估

練習重點：可觀測性、eval。

- 記錄每次 LLM 與工具呼叫的內容、耗時和 token 用量
- 建立固定的文章測試集和評分標準
- 用測試集比較不同模型與 prompt

### 階段 4.5：搜尋 agent

練習重點：新增第二個 agent、搜尋與引用。

- 新增 `web_search` 工具，與 Miniflux 工具分開
- 新增 `search` agent，回答時附上來源引用
- 加入 `--agent`，組裝層只建立所選 agent 需要的工具，並確認沒有動到 runtime（見 D-017）
- 用 eval 檢查引用是否真的出現在來源裡

### 階段 5：記憶與有副作用的工具

練習重點：持久化、長期記憶、人工確認流程。

- 保存對話紀錄
- 實作 `MemoryStore`，記住使用者感興趣的主題，讓摘要依興趣排序
- 實作 `Policy`，新增標記已讀工具，並在 CLI 上同步確認
- 防止文章內容被寫入長期記憶，例如標明來源或要求確認

### 階段 6：每日摘要推播

練習重點：常駐程序、排程、訊息介面。

- 新增通知通道（Slack、LINE、mail），只用來單向送出排程任務的結果；互動只透過 CLI 和 Web。通道和排程的設計還沒確定
- 每天定時產生摘要並推播到手機
- 需要在訊息平台上確認動作時，重新評估 D-005

### 階段 7：第二類 agent（家庭 agent）

練習重點：權限隔離、多使用者。

- 先做一個不涉及金錢的家庭功能
- 驗證只新增 agent 定義，不改動 runtime

長期構想見 `docs/vision.md`。

## Security enhancement

- 文章標題要標記為不可信內容（見 D-021）
- `fetch_page` 的位址檢查和實際連線之間 DNS 可能改變，要改成連線時檢查（見 D-021）

## 暫緩

- 通用工具：讀寫本地檔案
- Router、MCP（見 D-013）
- 可恢復的迴圈（見 D-005）

## 待決定

- **`summarize_entry` 的定位與 `DigestAgent` 的入口（階段 3 前）**：`SummarizeEntryTool`（見 D-022）實際上是掛在 `Tool` 介面下的流程：LLM 呼叫藏在工具裡，無法單獨換模型或回報進度，階段 4 的記錄也會漏掉。傾向抽出 `ArticleSummarizer`，工具和 `DigestAgent` 都呼叫它，問答留在 `LoopAgent`，批次摘要交給 workflow。D-004 否決了把 workflow 包成工具，所以 `DigestAgent` 要走 `--agent digest` 這類獨立入口，不能在同一段對話裡觸發；想在對話中觸發時，要先重新討論 D-004 或 router（見 D-013）。
- **Web 從哪裡打開（階段 2.5 的 Web 之前）**：只在服務所在的機器上打開時，綁定 `127.0.0.1` 就夠了；要從其他裝置打開時，要先加驗證，或透過 Tailscale、SSH tunnel（見 D-035）。
- **長期記憶的做法（階段 5 前）**：傾向由 agent 自己管理，使用小型常駐區塊加上 SQLite 或檔案。家庭事實要保留變更歷史。
- **家庭資料會傳給哪個 LLM 服務（階段 7 前）**：外部 API 或本地模型。
- **多模態的主要情境（加入 `ImagePart` 前）**：照片輸入可沿用現有設計，即時語音要另外設計。
