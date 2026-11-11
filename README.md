# agents-lab

一個可以對話的 RSS 分析 agent，讀取 Miniflux 的文章，回答趨勢、摘要和推薦的問題。
架構和設計決策見 `docs/`。

## 快速開始

```bash
uv sync
mkdir -p config
cp config.example.toml config/config.toml   # 填入 LLM 和 Miniflux 的網址、模型
$EDITOR prod.env                            # 填入密鑰，見「密鑰」
set -a; source prod.env; set +a
uv run python -m agent --config config/config.toml
```

要用 container 常駐執行，見「部署（container）」。

## 設定

設定分成兩個地方（見 D-038）：

- **設定檔** `config/config.toml`：網址、模型、任務等一般設定
- **環境變數**：只放密鑰

一個設定只會從其中一個地方讀取，環境變數不能覆蓋設定檔的值。`config.toml` 和 `*.env` 都已被 `.gitignore` 忽略，每台機器各自保存一份。設定檔放在 `config/` 目錄裡，本機和 container 用同一個位置。

### 指定設定檔

依下列順序找設定檔，兩個都沒有就無法啟動。程式不會在啟動目錄或其他固定位置裡找。

1. `--config <路徑>`
2. 環境變數 `AGENT_CONFIG`

```bash
uv run python -m agent --config config/config.toml
uv run python -m agent serve --config /srv/agents-lab/config/config.toml

export AGENT_CONFIG=config/config.toml   # 之後就不用每次加 --config
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

每行一個 `KEY=VALUE`，放在 `*.env` 檔案裡（例如 `prod.env`）。值不要加引號，也不要寫 `export`：`docker run --env-file` 不接受 `export`，也會把引號當成值的一部分，這個寫法在 shell、Docker 和之後的 k8s 都能用。

```bash
AGENT_LLM_API_KEY=sk-...
MINIFLUX_API_KEY=...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

在本機執行前，用 `set -a` 載入，變數才會傳給 `uv run` 啟動的程式；container 由 `compose.yaml` 的 `env_file` 載入（見「部署（container）」）：

```bash
set -a; source prod.env; set +a
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
config error: config/config.toml does not exist
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
uv run python -m agent --config config/config.toml
```

| 輸入 | 作用 |
| --- | --- |
| `/reset` | 開始新對話，舊對話不再送給模型（見 D-034） |
| `exit`、`quit` | 離開 |

## 透過服務對話

先啟動服務，再用終端機連過去。`chat` 不需要設定檔和密鑰，設定都在服務那一邊。

```bash
uv run python -m agent serve --config config/config.toml   # 終端機 1
uv run python -m agent chat                         # 終端機 2，預設連到 http://127.0.0.1:8000
uv run python -m agent chat --server http://127.0.0.1:9000
```

指令和在同一個程序裡對話時相同。服務沒有啟動時，每則訊息都會顯示連線錯誤，CLI 不會結束。

## HTTP API

```bash
uv run python -m agent serve --config config/config.toml                 # 預設監聽 127.0.0.1:8000
uv run python -m agent serve --config config/config.toml --port 9000
uv run python -m agent serve --config config/config.toml --host 0.0.0.0  # container 裡就是這樣啟動
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

服務本身不負責排程，定時觸發交給外部的排程器，目前用 cron，見「部署（container）」的「排程」。

## 部署（container）

用 Docker Compose 在一台機器上常駐執行服務，排程交給這台機器的 cron（見 D-039）。`deploy/` 裡的檔案：

| 檔案 | 作用 |
| --- | --- |
| `Dockerfile` | 建置 image：Python 3.14、只裝執行需要的套件、用非 root 使用者執行 `serve --host 0.0.0.0` |
| `compose.yaml` | 啟動 container：載入密鑰、掛上設定目錄、設定時區、只開放給這台機器的 `127.0.0.1:8000`，停止後自動重啟 |
| `crontab.example` | 定時呼叫 `POST /jobs/<名稱>/run` 的 crontab 範例 |

### 第一次部署

需要 Docker 和 Docker Compose。在部署的機器上取得專案後，在專案根目錄執行：

```bash
mkdir -p config
cp config.example.toml config/config.toml   # 修改設定和任務
$EDITOR prod.env                            # 填入密鑰，格式見「密鑰」
docker compose -f deploy/compose.yaml up -d --build
curl -fsS -X POST localhost:8000/sessions -H 'Content-Type: application/json' -d '{"owner": "cli"}'
```

最後一行回傳 `session_id` 就表示服務正常。也可以直接對話：`uv run python -m agent chat`。

container 裡的路徑：

| 來源 | container 裡 | 說明 |
| --- | --- | --- |
| `config/` | `/etc/agent/`（唯讀） | 讀 `/etc/agent/config.toml`，image 已經設定好 `AGENT_CONFIG` |
| `prod.env` | 環境變數 | 只放密鑰 |
| `TZ=Asia/Taipei` | 環境變數 | container 預設是 UTC，不設定時「今天」和「過去 24 小時」會差 8 小時；換時區時改 `compose.yaml` |

掛的是整個 `config/` 目錄，不是單一檔案。用 vim 等編輯器存檔時會換成新的檔案，只掛單一檔案的話 container 會一直讀到舊的內容。

### 排程

用 cron 定時觸發任務：

```bash
crontab -e   # 貼上 deploy/crontab.example 的內容，把任務名稱換成設定檔裡的名稱
```

```cron
0 8 * * * (date; curl -fsS --max-time 900 -X POST http://127.0.0.1:8000/jobs/daily-digest/run; echo) >> $HOME/agent-jobs.log 2>&1
15 8 * * * (date; curl -fsS --max-time 900 -X POST http://127.0.0.1:8000/jobs/weekly-ai/run; echo) >> $HOME/agent-jobs.log 2>&1
```

- 時間依照這台機器的時區，不是 container 的 `TZ`
- 多個任務要錯開時間，同時執行容易碰到 LLM 服務的每分鐘額度
- 機器在觸發時間沒有開機時，這次不會補跑
- 每次執行都會把時間和結果附加到 `~/agent-jobs.log`；失敗時會有 `curl: (22) ... error: 500` 這類訊息，狀態碼的意思見「排程任務與通知」

### 日常操作

| 要做的事 | 指令 |
| --- | --- |
| 看服務的記錄 | `docker compose -f deploy/compose.yaml logs -f` |
| 看排程的結果 | `tail -f ~/agent-jobs.log` |
| 修改任務 | 直接改 `config/config.toml` 的 `[jobs]`，下一次執行就生效 |
| 修改其他設定或密鑰 | 改完後 `docker compose -f deploy/compose.yaml up -d --force-recreate` |
| 更新程式 | `git pull` 後 `docker compose -f deploy/compose.yaml up -d --build` |
| 停止 | `docker compose -f deploy/compose.yaml down` |

注意：

- 重建或重啟 container 後，所有 session 都會遺失（同「HTTP API」）
- 服務只開放給這台機器。要讓區網的其他機器連進來，把 `compose.yaml` 的 `127.0.0.1:8000:8000` 改成 `8000:8000`。Docker 會直接修改 iptables，ufw 擋不住，而且服務沒有驗證，只能在內網這樣做（見 D-035）
- container 解析不到 Miniflux 的內網名稱時，在 `compose.yaml` 加上 `extra_hosts` 或 `dns`

## 開發

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

測試不需要設定檔和密鑰。
