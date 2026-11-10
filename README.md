# agents-lab

一個可以對話的 RSS 分析 agent，讀取 Miniflux 的文章，回答趨勢、摘要和推薦的問題。
架構和設計決策見 `docs/`。

## 快速開始

```bash
uv sync
cp config.example.toml config.toml   # 填入 LLM 和 Miniflux 的網址、模型
$EDITOR prod.env                     # 填入密鑰，見「密鑰」
source prod.env
uv run python -m agent --config config.toml
```

## 設定

設定分成兩個地方（見 D-038）：

- **設定檔** `config.toml`：網址、模型、任務等一般設定
- **環境變數**：只放密鑰

一個設定只會從其中一個地方讀取，環境變數不能覆蓋設定檔的值。`config.toml` 和 `*.env` 都已被 `.gitignore` 忽略，每台機器各自保存一份。

### 指定設定檔

依下列順序找設定檔，兩個都沒有就無法啟動。程式不會在啟動目錄或其他固定位置裡找。

1. `--config <路徑>`
2. 環境變數 `AGENT_CONFIG`

```bash
uv run python -m agent --config config.toml
uv run python -m agent serve --config /opt/agents-lab/config.toml

export AGENT_CONFIG=/opt/agents-lab/config.toml   # 之後就不用每次加 --config
uv run python -m agent serve
```

`--config` 寫在 `serve` 前面或後面都可以。`chat`（連到服務的客戶端）不需要設定檔。

### 設定檔

完整範例見 `config.example.toml`：

```toml
# debug = true

[llm]
base_url = "https://api.openai.com/v1"
model = "gpt-6-luna"
reasoning_effort = "none"

[miniflux]
base_url = "https://miniflux.example.com"
# ca_bundle = "/etc/ssl/miniflux-ca.pem"
# verify_ssl = false

[jobs.daily-digest]
prompt = "過去 24 小時的科技和新聞趨勢，各推薦最多 5 篇值得讀的文章"
channels = ["slack"]
```

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `debug` | 布林 | | `true` 時輸出 debug 記錄，預設 `false` |
| `llm.base_url` | 字串 | ✅ | OpenAI 相容 API 的網址 |
| `llm.model` | 字串 | ✅ | 模型名稱 |
| `llm.reasoning_effort` | 字串 | | 推理強度，有設定時才送出（見 D-023） |
| `llm.temperature` | 數字 | | 溫度，有設定時才送出 |
| `llm.system_prompt` | 字串 | | 取代 `rss` 的預設指令 |
| `miniflux.base_url` | 字串 | ✅ | Miniflux 的網址 |
| `miniflux.ca_bundle` | 字串 | | 自訂 CA 憑證的路徑 |
| `miniflux.verify_ssl` | 布林 | | `false` 時不檢查憑證，`ca_bundle` 也不會使用，預設 `true` |
| `jobs.<名稱>.prompt` | 字串 | 任務必填 | 送給 agent 的問題 |
| `jobs.<名稱>.channels` | 字串列表 | 任務必填 | 結果送到哪些通道，目前只有 `"slack"` |

布林值要寫成 `true`、`false`，不能加引號；`verify_ssl = "false"` 會被當成錯誤。`[jobs]` 可以完全不寫，見「排程任務與通知」。

### 密鑰

寫成 `export VAR=...`，放在 `*.env` 檔案裡（例如 `prod.env`），執行前先載入：

```bash
source prod.env
```

| 環境變數 | 必填 | 說明 |
| --- | --- | --- |
| `AGENT_LLM_API_KEY` | ✅ | LLM 服務的 API 金鑰 |
| `MINIFLUX_API_KEY` | ✅ | Miniflux 的 API 金鑰 |
| `SLACK_WEBHOOK_URL` | | Slack incoming webhook 的網址，沒有設定時不能使用 `slack` 通道 |
| `AGENT_CONFIG` | | 設定檔的路徑，`--config` 優先 |

### 什麼時候生效

| 修改 | 生效時機 |
| --- | --- |
| `[jobs]` | 下一次執行任務時，不用重啟 |
| 其他設定、密鑰 | 重啟服務後 |

### 設定錯誤

啟動時就會檢查設定和密鑰，有錯時印出訊息後結束，不會等到第一次使用才失敗：

```text
config error: no config file: pass --config <path> or set AGENT_CONFIG
config error: /opt/agents-lab/config.toml does not exist
config error: llm.model is required
config error: miniflux.verify_ssl must be true or false: 'false'
config error: AGENT_LLM_API_KEY must be set in the environment
```

`[jobs]` 不在啟動時檢查，任務寫錯時在觸發那次才會報錯。

### 從舊的環境變數換過來

2026-11-10 以前的設定都放在環境變數裡，現在已經不再讀取。搬到設定檔的對照：

| 舊的環境變數 | 設定檔 |
| --- | --- |
| `AGENT_LLM_BASE_URL` | `llm.base_url` |
| `AGENT_LLM_MODEL` | `llm.model` |
| `AGENT_LLM_REASONING_EFFORT` | `llm.reasoning_effort` |
| `AGENT_LLM_TEMPERATURE` | `llm.temperature`（改成數字，不加引號） |
| `AGENT_SYSTEM_PROMPT` | `llm.system_prompt` |
| `MINIFLUX_BASE_URL` | `miniflux.base_url` |
| `MINIFLUX_CA_BUNDLE` | `miniflux.ca_bundle` |
| `MINIFLUX_VERIFY_SSL` | `miniflux.verify_ssl`（改成 `true` 或 `false`） |
| `AGENT_DEBUG` | `debug = true` |
| `AGENT_JOBS_FILE` 指向的 `jobs.toml` | 裡面的 `[jobs.*]` 直接搬進設定檔 |

搬完後，`prod.env` 只需要留下「密鑰」那一節列出的變數，留著舊的也不會報錯。

## 在終端機對話

```bash
uv run python -m agent --config config.toml
```

| 輸入 | 作用 |
| --- | --- |
| `/reset` | 開始新對話，舊對話不再送給模型（見 D-034） |
| `exit`、`quit` | 離開 |

## 透過服務對話

先啟動服務，再用終端機連過去。`chat` 不需要設定檔和密鑰，設定都在服務那一邊。

```bash
uv run python -m agent serve --config config.toml   # 終端機 1
uv run python -m agent chat                         # 終端機 2，預設連到 http://127.0.0.1:8000
uv run python -m agent chat --server http://127.0.0.1:9000
```

指令和在同一個程序裡對話時相同。服務沒有啟動時，每則訊息都會顯示連線錯誤，CLI 不會結束。

## HTTP API

```bash
uv run python -m agent serve --config config.toml                 # 預設監聽 127.0.0.1:8000
uv run python -m agent serve --config config.toml --port 9000
uv run python -m agent serve --config config.toml --host 0.0.0.0  # 例如在 container 裡
```

監聽的位址和 port 只能用參數指定，不放在設定檔裡。服務沒有驗證：預設只監聽 `127.0.0.1`，用 `--host` 開放到其他位址時，只能在內網使用（見 D-035）。

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
- session 保留 7 天，排程任務的 session 最多保留 7 個；每個 owner 目前的 session 不會被刪除（見 D-036）
- 服務重啟後，所有 session 都會遺失

## 排程任務與通知

任務寫在設定檔裡，每個任務是一個 `[jobs.<名稱>]` 區塊，名稱就是觸發時 URL 裡的 `{name}`，欄位見「設定檔」：

```toml
[jobs.daily-digest]
prompt = "過去 24 小時的科技和新聞趨勢，各推薦最多 5 篇值得讀的文章"
channels = ["slack"]

[jobs.weekly-ai]
prompt = "過去 7 天 AI 相關的重要發展，推薦最多 5 篇"
channels = ["slack"]
```

任務是選用的。設定檔沒有 `[jobs]` 時，`/jobs/{name}/run` 一樣存在，觸發時回傳 `404`。修改任務不用重啟服務，服務啟動後用 HTTP 觸發一個任務：

```bash
curl -fsS -X POST localhost:8000/jobs/daily-digest/run
```

服務會等任務做完才回應（見 D-037）：

| 狀態碼 | 意思 |
| --- | --- |
| `200` | 已送出，回傳 `session_id` |
| `502` | agent 失敗，錯誤通知已送出 |
| `500` | 通知送不出去、任務用了沒有設定的通道，或任務的欄位寫錯 |
| `404` | 設定檔裡沒有這個任務 |

服務本身不負責排程，定時觸發交給外部的排程器，例如下面的 systemd timer 或 cron。

## 部署（systemd）

`deploy/` 是範例，複製到 `/etc/systemd/system/` 後，依機器修改路徑和使用者：

| 檔案 | 作用 |
| --- | --- |
| `agent.service` | 常駐執行 `python -m agent serve`，先 `source prod.env` 載入密鑰，再用 `--config /opt/agents-lab/config.toml` 啟動 |
| `agent-job@.service` | 所有任務共用的範本：`agent-job@<名稱>.service` 用 `curl` 呼叫一次 `POST /jobs/<名稱>/run`，失敗時結束代碼不是 0 |
| `agent-job@daily-digest.timer` | 每天 08:00（機器的時區）觸發 `daily-digest`，錯過時會在開機後補跑 |

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now agent.service agent-job@daily-digest.timer
systemctl list-timers 'agent-job@*'
journalctl -u agent.service -u 'agent-job@*'
```

timer 的名稱要和設定檔裡的任務名稱一致。新增任務時，service 不用改，只要複製一份 timer，把 `@` 後面換成任務名稱，再修改 `OnCalendar=`：

```bash
sudo cp /etc/systemd/system/agent-job@daily-digest.timer /etc/systemd/system/agent-job@weekly-ai.timer
sudo systemctl daemon-reload
sudo systemctl enable --now agent-job@weekly-ai.timer
```

## 開發

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

測試不需要設定檔和密鑰。
