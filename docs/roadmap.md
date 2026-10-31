# 發展方向

> 目標：以練習 agent 技術和架構設計為主，並做出實際有用的 RSS 摘要工具。決策原因見 `docs/decisions.md`。

## 目前能力

- 終端機多輪對話，對話記憶只存在記憶體
- 支援任何 OpenAI 相容 API
- 工具呼叫迴圈
- 用 Miniflux 工具查詢 RSS 文章的標題、feed、已讀狀態和網址
- 用 `rich` 渲染 Markdown 回覆

## 已知問題

- [ ] `Chat.send()` 收齊回覆才輸出，使用者看不到逐字串流
- [ ] LLM 不知道今天日期，「最近一週」這類查詢可能算錯日期範圍
- [ ] Miniflux 工具只回傳標題等資訊，不含文章內容，無法摘要文章
- [ ] 對話歷史會無限增長，長對話可能超過模型的 context 上限
- [ ] 對話在程式結束後就消失

## 路線

### 階段 0：穩定基礎（已完成）

- 修正工具呼叫上限的 bug（見 D-014）
- 讓 CLI 能處理 LLM 錯誤，不會中斷對話

### 階段 1：架構拆解

練習重點：Clean Architecture、元件邊界。目標元件見 `docs/architecture.md`。

- 把 `Chat` 拆成 `LoopAgent`、`AgentSpec`、`ConversationStore`
- 新增 `Agent`、`AgentRequest`、`Event`、`ContextBuilder`、`ToolRegistry`
- `Message` 改成內容區塊，先只實作 `TextPart`
- CLI 加上 `--agent`，用 `general` 和 `rss` 驗證新增 agent 不需要改動 runtime

### 階段 2：單篇與少量文章摘要

練習重點：工具設計、system prompt 設計。

- 讓 LLM 知道今天日期
- 新增讀取文章內容的工具
- 完成「摘要這篇文章」和「摘要今天的未讀文章」
- 把文章內容視為不可信資料，防範 prompt injection

### 階段 3：大量文章摘要

練習重點：context 管理、token 計算、map-reduce、workflow。

- 計算 token 用量
- 在 `ContextBuilder` 修剪或壓縮歷史，優先清除舊的工具結果
- 實作 `DigestAgent`：先逐篇摘要，再彙整成總覽

### 階段 4：摘要品質評估

練習重點：可觀測性、eval。

- 記錄每次 LLM 與工具呼叫的內容、耗時和 token 用量
- 建立固定的文章測試集和評分標準
- 用測試集比較不同模型與 prompt

### 階段 5：記憶與有副作用的工具

練習重點：持久化、長期記憶、人工確認流程。

- 保存對話紀錄
- 實作 `MemoryStore`，記住使用者感興趣的主題，讓摘要依興趣排序
- 實作 `Policy`，新增標記已讀工具，並在 CLI 上同步確認
- 防止文章內容被寫入長期記憶，例如標明來源或要求確認

### 階段 6：每日摘要推播

練習重點：常駐程序、排程、訊息介面。

- 新增訊息平台 adapter（Telegram 或 LINE）
- 每天定時產生摘要並推播到手機
- 需要在訊息平台上確認動作時，重新評估 D-005

### 階段 7：第二類 agent（家庭 agent）

練習重點：權限隔離、多使用者。

- 先做一個不涉及金錢的家庭功能
- 驗證只新增 agent 定義，不改動 runtime

長期構想見 `docs/vision.md`。

## 暫緩

- 通用工具：網頁搜尋、讀取網頁、讀寫本地檔案
- Web UI
- Router、MCP（見 D-013）
- 可恢復的迴圈（見 D-005）

## 待決定

- **長期記憶的做法（階段 5 前）**：傾向由 agent 自己管理，使用小型常駐區塊加上 SQLite 或檔案。家庭事實要保留變更歷史。
- **家庭資料會傳給哪個 LLM 服務（階段 7 前）**：外部 API 或本地模型。
- **多模態的主要情境（加入 `ImagePart` 前）**：照片輸入可沿用現有設計，即時語音要另外設計。
