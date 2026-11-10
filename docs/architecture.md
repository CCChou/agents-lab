# 架構

目標是把共用機制拆成元件，讓新增 agent 不需要改動 runtime。設計原因見 `docs/decisions.md`。

> **注意**：本文件同時描述現況與目標設計。實作前先看「現況」欄，標示「計畫中」的元件尚不存在。

## 分層

採用 Clean Architecture，所有依賴最後都指向 `domain`。`*` 代表先保留位置、後續階段才實作。

```text
┌─ composition ─────────────────────────────────────────┐
│  __main__.py    config.py    agents/*.py              │
└───────────────────────────┬───────────────────────────┘
                            │ wires everything
                            ▼
┌─ entry adapters ──────────────────────────────────────┐
│  CLI          HTTP API          LINE*      Scheduler* │
└──────────┬────────────────────────────────▲───────────┘
           │ owner_id → session_id          │
           │ AgentRequest                   │ Event
           ▼                                │
┌─ use_cases ───────────────────────────────┴───────────┐
│  Session lifecycle:                                   │
│    SessionManager                                     │
│  Job delivery:                                        │
│    RunJob                                             │
│  Agent implementations:                               │
│    LoopAgent(spec)        DigestAgent*                │
│  Shared by LoopAgent:                                 │
│    ContextBuilder         ToolRegistry                │
│  Tools:                                               │
│    SummarizeEntryTool                                 │
└───────────────────────────┬───────────────────────────┘
                            │ depends on
                            ▼
┌─ domain ──────────────────────────────────────────────┐
│  Ports: Agent  LLMClient  Tool  Policy*               │
│         ConversationStore  SessionRegistry            │
│         SessionLifecycle                              │
│         Notifier  JobSource                           │
│         MemoryStore*  BlobStore*  ArticleReader       │
│  Data:  AgentSpec  AgentRequest  Event                │
│         Message  ContentPart  ToolCall  Article       │
│         SessionInfo  RetentionRule  Job  Notification │
└───────────────────────────▲───────────────────────────┘
                            │ implements
┌─ infrastructure adapters ─┴───────────────────────────┐
│  OpenAICompatibleLLMClient    MinifluxQueryTool       │
│  InMemorySessionStore         MinifluxGetEntryTool    │
│  CurrentTimeTool              FetchPageTool           │
│  MinifluxArticleReader        SqliteStores*           │
│  MinifluxListCategoriesTool                           │
│  MinifluxCountEntriesByCategoryTool                   │
│  RemoteAgent                  RemoteSessions          │
│  SlackWebhookNotifier         TomlJobSource           │
└───────────────────────────────────────────────────────┘
```

## 元件

| 元件 | 層 | 職責 | 現況 |
| --- | --- | --- | --- |
| `Agent` | domain 介面 | 所有 agent 的共同入口：收請求、出事件 | 已實作 |
| `LoopAgent` | use_cases | 通用工具迴圈，由 LLM 決定流程 | 已實作 |
| `AgentSpec` | domain 資料 | 定義對話型 agent：指令、模型、工具、迴圈上限、單一工具的每輪上限 | 已實作，定義放在 `agent/agents/` |
| `AgentRequest` | domain 資料 | 統一的輸入格式：session 和使用者訊息 | 已實作 |
| `Event` | domain 資料 | 統一的輸出格式 | 已實作：`TextDelta`、`ToolStarted`、`ToolLimitReached` |
| `ContextBuilder` | use_cases | 組合指令、記憶和對話，並修剪 context | 已實作，目前組合指令和對話，並清除舊的工具結果 |
| `ToolRegistry` | use_cases | 依名稱找到工具，名稱不存在時在啟動就報錯 | 已實作 |
| `ConversationStore` | domain 介面 | Session 的內容角色：依 session 讀寫和刪除訊息 | 已實作，目前只有 `InMemorySessionStore` |
| `SessionRegistry` | domain 介面 | Session 的生命週期角色：記住每個 owner 有哪些 session、建立時間，以及目前用哪個（見 D-034、D-036） | 已實作，目前只有 `InMemorySessionStore` |
| `SessionManager` | use_cases | 管理 session 生命週期，是唯一同時處理兩個 session 角色的元件；開新 session 時依 `RetentionRule` 回收舊的（見 D-034、D-036） | 已實作 `current_or_start`、`start_new`、`prune`；`resume`、`clear`、列出 session 計畫中 |
| HTTP API | entry adapters | 用 HTTP 提供 session 和 SSE 事件串流，只綁定 `127.0.0.1`（見 D-035） | 已實作 `POST /sessions`、`POST /sessions/{id}/messages`、`POST /jobs/{name}/run` |
| `wire` | adapters | HTTP 邊界的傳輸 DTO，以及和 `Event` 互相轉換的函式，服務端和客戶端共用（見 D-035） | 已實作 |
| `SessionLifecycle` | domain 介面 | 入口取得和開新 session 的方式，讓 CLI 可以換成遠端版本（見 D-035） | 已實作，由 `SessionManager` 和 `RemoteSessions` 實作 |
| `RemoteAgent` | adapters | 透過 HTTP API 實作 `Agent`，把 SSE 還原成 `Event`，收到 `turn_failed` 或串流提前結束時丟出例外 | 已實作 |
| `RemoteSessions` | adapters | 透過 HTTP API 實作 `SessionLifecycle`，在客戶端記住每個 owner 目前的 session | 已實作 |
| `RunJob` | use_cases | 執行排程任務：以 owner `job:{name}` 開 session、呼叫 `Agent`、把回答交給每個通道，失敗時送錯誤通知（見 D-037） | 已實作 |
| `Job`、`Notification` | domain 資料 | 任務定義（`name`、`prompt`、`channels`）和要送出的通知（`title`、`markdown`、`session_id`） | 已實作 |
| `Notifier` | domain 介面 | 把一份通知送到一個通道 | 已實作，目前只有 `SlackWebhookNotifier`（在 adapter 裡轉成 mrkdwn） |
| `JobSource` | domain 介面 | 依名稱取得任務定義 | 已實作，目前只有 `TomlJobSource`，每次都重新讀取設定檔的 `[jobs]`（見 D-038） |
| `LLMClient` | domain 介面 | 呼叫模型，隱藏供應商差異 | 已實作 |
| `Tool` | domain 介面 | 定義工具 | 已實作，`run()` 目前回傳字串 |
| `Message` | domain 資料 | 對話訊息 | 已實作，`ContentPart` 目前只有 `TextPart` |
| `ToolCall` | domain 資料 | LLM 要求的工具呼叫 | 已實作 |
| `ArticleReader` | domain 介面 | 依文章 id 讀取內容 | 已實作，目前只有 `MinifluxArticleReader` |
| `Article` | domain 資料 | 文章的中繼資料和純文字內文 | 已實作 |
| `SummarizeEntryTool` | use_cases | 用獨立的 LLM 請求摘要一篇文章（見 D-022） | 已實作 |
| `Policy` | domain 介面 | 判斷工具呼叫要允許、確認或拒絕 | 計畫中（階段 5） |
| `MemoryStore` | domain 介面 | 長期記憶，依問題和範圍搜尋 | 計畫中（階段 5） |
| `BlobStore` | domain 介面 | 保存圖片等檔案 | 計畫中，需要多模態時才加 |
| `DigestAgent` | use_cases | 第一個 workflow：大量文章摘要 | 計畫中（階段 3） |

## 邊界規則

- 入口只透過 `Agent` 介面溝通，不知道背後是哪種實作。
- 由 LLM 決定流程的 agent 使用 `AgentSpec` + `LoopAgent`；由程式決定流程的 workflow 自行實作 `Agent`。
- `LoopAgent` 不知道模型或工具的具體實作，一律透過介面使用。
- 組裝層依 `AgentSpec` 指定的模型建立 `LLMClient`；`model` 為 `None` 時使用設定檔的預設模型（`llm.model`）。
- `LoopAgent` 只能使用 `AgentSpec` 列出的工具，即使 registry 裡有其他工具。
- 訊息只保存檔案參照，不保存檔案內容。
- 入口不產生 session id，只提供 owner，透過 `SessionManager` 取得目前的 session。指令文字（例如 `/reset`）由入口解析。
- `LoopAgent` 和 `ContextBuilder` 只認 `session_id`，不知道 owner 和 session 生命週期。
- HTTP 邊界用 `wire` 的 DTO，不直接序列化 domain 的型別；`turn_completed` 和 `turn_failed` 只存在於傳輸層。
- 產生內容和送出內容分開：`Agent` 的實作只產生內容，不知道通知；送出只由 `RunJob` 負責，agent 沒有送出訊息的工具。模型一律輸出 Markdown，各通道的格式在 `Notifier` 的 adapter 裡轉換。
- `ConversationStore` 和 `SessionRegistry` 是同一個 Session 概念的兩個角色，由同一個 adapter 實作；需要同時處理兩者的操作只放在 `SessionManager`。

## 現行訊息流程（`LoopAgent`）

1. `cli.run` 讀取輸入，向 `SessionManager` 取得 owner `cli` 目前的 session，再呼叫 `Agent.run()`。輸入 `/reset` 時改成開新的 session，不呼叫 agent（見 D-034）。輸入來源和文字輸出方式由組裝層決定（見 D-026）。
2. `LoopAgent` 透過 `ContextBuilder` 取得 system prompt 和歷史，加上新訊息，連同 `AgentSpec` 列出的工具送給 `LLMClient.stream()`。
3. LLM 的文字以 `TextDelta` 即時輸出。沒有工具呼叫時，結束這一輪。
4. LLM 要求呼叫工具時，`LoopAgent` 輸出 `ToolStarted` 並執行工具，把結果加入這一輪的訊息，再回到第 2 步。超過 `AgentSpec.tool_call_limits` 的呼叫不執行，改回傳未執行的結果（見 D-025）。
5. 第 2 到 4 步最多執行 `AgentSpec.max_tool_iterations` 次（預設 5，`rss` 為 10）。達到上限時，補上工具結果，再以不提供工具的方式要求 LLM 回答一次。

工具執行失敗或工具不存在時，錯誤訊息會回傳給 LLM，不會中斷對話。這一輪完成後，才把訊息寫入 `ConversationStore`。LLM 呼叫失敗時，這一輪不會保存，`cli.run` 顯示錯誤並繼續對話。

## 擴充方式

### 新增工具（現行）

1. 在 `tests/adapters/` 先寫失敗的測試。
2. 在 `agent/adapters/` 實作 `Tool` Protocol。
3. 在 `agent/__main__.py` 的 `_build_tools()` 註冊。

### 新增 agent

- 對話型：在 `agent/agents/` 新增一個 `AgentSpec`。
- Workflow：實作 `Agent`。

目前 `__main__.py` 只組裝 `rss`。新增第二個 agent 時，要同時加入選擇 agent 的方式（見 D-017）。

如果新增 agent 需要改動 runtime，代表元件拆分有問題，要先提出來討論。

## 測試方式

- Use case 測試用假的 `LLMClient`，不打真實 API。
- Adapter 測試注入假的依賴，例如 `chat_model` 或 HTTP client。

## 執行方式

安裝、設定檔、終端機對話和 HTTP API 的用法見 `README.md`。
