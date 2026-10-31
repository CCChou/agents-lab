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
│  CLI              LINE*              Scheduler*       │
└──────────┬────────────────────────────────▲───────────┘
           │ AgentRequest                   │ Event
           ▼                                │
┌─ use_cases ───────────────────────────────┴───────────┐
│  Agent implementations:                               │
│    LoopAgent(spec)        DigestAgent*                │
│  Shared by LoopAgent:                                 │
│    ContextBuilder         ToolRegistry                │
└───────────────────────────┬───────────────────────────┘
                            │ depends on
                            ▼
┌─ domain ──────────────────────────────────────────────┐
│  Ports: Agent  LLMClient  Tool  Policy*               │
│         ConversationStore  MemoryStore*  BlobStore*   │
│  Data:  AgentSpec  AgentRequest  Event                │
│         Message  ContentPart  ToolCall                │
└───────────────────────────▲───────────────────────────┘
                            │ implements
┌─ infrastructure adapters ─┴───────────────────────────┐
│  OpenAICompatibleLLMClient    MinifluxQueryTool       │
│  InMemoryConversationStore    SqliteStores*           │
└───────────────────────────────────────────────────────┘
```

## 元件

| 元件 | 層 | 職責 | 現況 |
| --- | --- | --- | --- |
| `Agent` | domain 介面 | 所有 agent 的共同入口：收請求、出事件 | 已實作 |
| `LoopAgent` | use_cases | 通用工具迴圈，由 LLM 決定流程 | 已實作 |
| `AgentSpec` | domain 資料 | 定義對話型 agent：指令、模型、工具、工具上限 | 已實作，定義放在 `agent/agents/` |
| `AgentRequest` | domain 資料 | 統一的輸入格式：session 和使用者訊息 | 已實作 |
| `Event` | domain 資料 | 統一的輸出格式 | 已實作：`TextDelta`、`ToolStarted`、`ToolLimitReached` |
| `ContextBuilder` | use_cases | 組合指令、記憶和對話，並修剪 context | 已實作，目前只組合指令和對話 |
| `ToolRegistry` | use_cases | 依名稱找到工具，名稱不存在時在啟動就報錯 | 已實作 |
| `ConversationStore` | domain 介面 | 短期記憶，依 session 讀寫 | 已實作，目前只有 `InMemoryConversationStore` |
| `LLMClient` | domain 介面 | 呼叫模型，隱藏供應商差異 | 已實作 |
| `Tool` | domain 介面 | 定義工具 | 已實作，`run()` 目前回傳字串 |
| `Message` | domain 資料 | 對話訊息 | 已實作，`ContentPart` 目前只有 `TextPart` |
| `ToolCall` | domain 資料 | LLM 要求的工具呼叫 | 已實作 |
| `Policy` | domain 介面 | 判斷工具呼叫要允許、確認或拒絕 | 計畫中（階段 5） |
| `MemoryStore` | domain 介面 | 長期記憶，依問題和範圍搜尋 | 計畫中（階段 5） |
| `BlobStore` | domain 介面 | 保存圖片等檔案 | 計畫中，需要多模態時才加 |
| `DigestAgent` | use_cases | 第一個 workflow：大量文章摘要 | 計畫中（階段 3） |

## 邊界規則

- 入口只透過 `Agent` 介面溝通，不知道背後是哪種實作。
- 由 LLM 決定流程的 agent 使用 `AgentSpec` + `LoopAgent`；由程式決定流程的 workflow 自行實作 `Agent`。
- `LoopAgent` 不知道模型或工具的具體實作，一律透過介面使用。
- 組裝層依 `AgentSpec` 指定的模型建立 `LLMClient`；`model` 為 `None` 時使用環境變數的預設模型。
- `LoopAgent` 只能使用 `AgentSpec` 列出的工具，即使 registry 裡有其他工具。
- 訊息只保存檔案參照，不保存檔案內容。

## 現行訊息流程（`LoopAgent`）

1. `cli.run` 讀取輸入，呼叫 `Agent.run()`。
2. `LoopAgent` 透過 `ContextBuilder` 取得 system prompt 和歷史，加上新訊息，連同 `AgentSpec` 列出的工具送給 `LLMClient.stream()`。
3. LLM 的文字以 `TextDelta` 即時輸出。沒有工具呼叫時，結束這一輪。
4. LLM 要求呼叫工具時，`LoopAgent` 輸出 `ToolStarted` 並執行工具，把結果加入這一輪的訊息，再回到第 2 步。
5. 第 2 到 4 步最多執行 `AgentSpec.max_tool_iterations` 次（預設 5）。達到上限時，補上工具結果，再以不提供工具的方式要求 LLM 回答一次。

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

`uv run python -m agent`。環境變數見 `agent/config.py`，`AGENT_DEBUG` 見 `agent/__main__.py`。`rss` agent 需要 Miniflux 設定才能啟動。
