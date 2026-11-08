# agents-lab

一個可以對話的 RSS 分析 agent，讀取 Miniflux 的文章，回答趨勢、摘要和推薦的問題。
架構和設計決策見 `docs/`。

## 安裝

```bash
uv sync
```

## 設定

把環境變數寫成 `export VAR=...`，放在 `*.env` 檔案裡（例如 `prod.env`、`test.env`，已被 `.gitignore` 忽略），執行前先載入：

```bash
source prod.env
```

| 環境變數 | 必填 | 說明 |
| --- | --- | --- |
| `AGENT_LLM_BASE_URL` | ✅ | OpenAI 相容 API 的網址 |
| `AGENT_LLM_API_KEY` | ✅ | API 金鑰 |
| `AGENT_LLM_MODEL` | ✅ | 模型名稱 |
| `AGENT_LLM_TEMPERATURE` | | 溫度 |
| `AGENT_LLM_REASONING_EFFORT` | | 推理強度（見 D-023） |
| `AGENT_SYSTEM_PROMPT` | | 覆蓋 `rss` 的預設指令 |
| `MINIFLUX_BASE_URL` | ✅ | Miniflux 的網址 |
| `MINIFLUX_API_KEY` | ✅ | Miniflux 的 API 金鑰 |
| `MINIFLUX_CA_BUNDLE` | | 自訂 CA 憑證的路徑 |
| `MINIFLUX_VERIFY_SSL` | | 設成 `false` 可以關閉憑證檢查，預設是 `true` |
| `AGENT_DEBUG` | | 有設定時輸出 debug 記錄 |

## 在終端機對話

```bash
uv run python -m agent
```

| 輸入 | 作用 |
| --- | --- |
| `/reset` | 開始新對話，舊對話不再送給模型（見 D-034） |
| `exit`、`quit` | 離開 |

## HTTP API

```bash
uv run python -m agent serve            # 預設 port 8000，只監聽 127.0.0.1（見 D-035）
uv run python -m agent serve --port 9000
```

### `POST /sessions`

開一個新的 session。

```bash
curl -s -X POST localhost:8000/sessions \
  -H 'Content-Type: application/json' -d '{"owner": "cli"}'
# 201 {"session_id": "a1b2..."}
```

### `POST /sessions/{session_id}/messages`

送出一則訊息，回應是 SSE 事件串流（`text/event-stream`），每個事件都是一行 `data: <JSON>`。

```bash
curl -N -X POST "localhost:8000/sessions/$sid/messages" \
  -H 'Content-Type: application/json' -d '{"text": "今天科技新聞有什麼趨勢？"}'
```

| `type` | 欄位 | 說明 |
| --- | --- | --- |
| `text_delta` | `text` | 回答的一段文字 |
| `tool_started` | `name`、`arguments` | 開始使用工具 |
| `tool_limit_reached` | | 達到工具呼叫上限 |
| `turn_completed` | | 這一輪完成並已保存，串流結束 |
| `turn_failed` | `error` | 這一輪失敗，沒有保存，串流結束 |

完整定義見 `agent/adapters/http/wire.py`。注意：

- 中途斷線時，這一輪不會保存
- 送到不存在的 session id 不會報錯，會被當成新的空對話
- 服務重啟後，所有 session 都會遺失

## 開發

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
