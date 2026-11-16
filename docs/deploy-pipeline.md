# 部署流程

從筆電上的一個 commit 到常駐機器上跑起來的步驟（見 D-040、D-041）。筆電用 colima 和 Docker 建置，常駐機器是 RHEL 9.6，由 root 用 Podman 執行（rootful）。目前全部手動執行，每一步都寫明通過條件，以後可以照著換成 git hook、GitHub Actions 或 k8s。任何一步沒通過就停下來，不要往下做。

| 階段 | 在哪裡 | 以後可以交給 |
| --- | --- | --- |
| 1. 前置檢查與驗證 | 筆電 | `pre-push` hook，或推到 `main` 時的 GitHub Actions |
| 2. 建置與推送 | 筆電 | GitHub Actions |
| 3. 部署與驗證 | 常駐機器 | 用 SSH 執行的 script，改成 k8s 後交給 Deployment |

image 的 tag 一律用 commit 的短 sha。`latest` 只在常駐機器驗證過後才移過去，所以 `latest` 永遠是最後一個驗證過的版本，`compose.prod.yaml` 沒有指定 `AGENT_IMAGE_TAG` 時用的就是它。

## 第一次準備

只需要做一次。

**筆電**

```bash
brew install docker-buildx
# colima 預設不能建置 amd64 的 image，二選一：
docker run --privileged --rm tonistiigi/binfmt --install amd64
# colima stop && colima start --vm-type vz --vz-rosetta

# GitHub 的 personal access token（classic），要有 write:packages，記下到期日
echo "$GHCR_TOKEN" | docker login ghcr.io -u CCChou --password-stdin
```

**常駐機器（RHEL 9.6，以下都用 root 執行）**

```bash
# podman-compose 在 EPEL 裡，EPEL 需要 CodeReady Builder
subscription-manager repos --enable codeready-builder-for-rhel-9-$(arch)-rpms
dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
dnf install -y podman podman-compose git cronie
systemctl enable --now crond

git clone https://github.com/CCChou/agents-lab.git ~/agents-lab && cd ~/agents-lab   # public repo，不用 SSH key
mkdir -p config
cp config.example.toml config/config.toml   # 修改設定和任務，見 README 的「設定」
$EDITOR prod.env                            # 只放密鑰，見 README 的「密鑰」
chmod 755 config && chmod 644 config/*.toml # container 裡用 uid 10001 讀，要讓其他人可讀
chmod 600 prod.env                          # 由 podman 在主機上讀，不用給 container
podman login ghcr.io -u CCChou              # 這台的 token 只需要 read:packages，記下到期日
podman compose -f deploy/compose.prod.yaml config   # 看得懂 name 和 ${AGENT_IMAGE_TAG:-latest}

# 用 systemd 管理 compose：開機時啟動，systemctl start/stop/restart 操作
mkdir -p /etc/agents-lab
ln -s /root/agents-lab/deploy/agents-lab.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable agents-lab        # 第一次部署的 3.4 才啟動
```

`agents-lab.service` 從 `/etc/agents-lab/image.env` 讀 `AGENT_IMAGE_TAG`，每次部署時寫入，所以重開機後跑的是最後部署的版本，不是 `latest`。不要另外啟用 `podman-restart.service`，開機啟動只交給這個 unit；container 自己結束時，由 compose 的 `restart: always` 重啟。unit 用連結的方式安裝，`git checkout` 換版本時也會跟著換，unit 有變更時要 `systemctl daemon-reload`。

`config/` 會被 compose 的 `:Z` 重新標上 SELinux 標籤，只給這個 container 用。

container 解析不到 Miniflux 的內網名稱時，在這台建立不進版控的 `deploy/compose.hosts.yaml`（`extra_hosts` 或 `dns`），並在 unit 的 `ExecStart`、`ExecStop` 和下面的 `podman compose` 指令都加上 `-f deploy/compose.hosts.yaml`。目前的常駐機器不需要。

第一次部署時還沒有舊版可以退回，第 3 階段失敗時只能修好後重新跑一次流程。

## 1. 前置檢查與驗證（筆電）

```bash
git switch main
git status --porcelain          # 沒有輸出
git fetch && git status -sb     # 第一行是 "## main...origin/main"，沒有 ahead 或 behind
uv sync --locked
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

通過條件：工作目錄乾淨、`main` 和 `origin/main` 相同、每個指令都回傳 0。

image 用 commit 的 sha 當 tag，所以工作目錄有沒 commit 的修改時，image 會和 tag 對不上。改成 hook 時，這一步的檢查還是要留在第 2 階段，因為 hook 可以用 `--no-verify` 跳過，`.git/hooks` 也不進版控（要放在 `.githooks/` 並設定 `core.hooksPath`）。

## 2. 建置與推送（筆電）

```bash
test -z "$(git status --porcelain)"   # 再確認一次，建置的就是驗證過的 commit
sha=$(git rev-parse --short HEAD)
docker buildx build --platform linux/amd64 -f deploy/Dockerfile \
  -t "ghcr.io/ccchou/agents-lab:$sha" --push .
docker buildx imagetools inspect "ghcr.io/ccchou/agents-lab:$sha"
```

通過條件：推送成功，`imagetools inspect` 列出 `linux/amd64`。

這裡不在筆電上跑 smoke test：`compose.local.yaml` 已經驗證過 Dockerfile 和啟動流程，amd64 只差在套件的 wheel。只推 sha，不動 `latest`。

## 3. 部署與驗證（常駐機器）

### 3.1 選時間

避開 07:50–08:30。`up -d` 會換掉 container，正在執行的任務會中斷，那天的推播不會補送（D-039）；記憶體裡的 session 也會消失。

### 3.2 記錄目前的版本

```bash
cd ~/agents-lab
sha=<第 2 階段的 sha>
prev=$(sed -n 's/^AGENT_IMAGE_TAG=//p' /etc/agents-lab/image.env 2>/dev/null)
prev=${prev:-$(git rev-parse --short HEAD)}   # 第一次部署還沒有 image.env
echo "$(date -Iseconds) deploy $prev -> $sha" >> ~/agent-deploys.log
```

`prev` 是目前在跑的版本，也是退回時要用的 tag。

### 3.3 比對設定有沒有變更

```bash
git fetch
git diff "$prev" "$sha" -- config.example.toml agent/config.py
```

通過條件：沒有輸出，或已經照著差異更新 `config/config.toml` 和 `prod.env`。設定檔不進版控，新版多了必填欄位或密鑰時，container 會在啟動時因為 `config error` 結束。

### 3.4 切到同一個 commit 並啟動

```bash
git checkout "$sha"     # compose、crontab 和 unit 要和 image 是同一個 commit，不用 git pull
echo "AGENT_IMAGE_TAG=$sha" > /etc/agents-lab/image.env
AGENT_IMAGE_TAG=$sha podman compose -f deploy/compose.prod.yaml pull   # 先拉好，restart 時不用等
systemctl daemon-reload                # unit 有變更時才需要，執行也無妨
systemctl restart agents-lab
systemctl status agents-lab --no-pager
podman ps
```

通過條件：`status` 是 `active (exited)`（oneshot 的正常狀態），`podman ps` 裡的 container 是 `Up`，image 是 `ghcr.io/ccchou/agents-lab:$sha`。`git checkout` 之後是 detached HEAD，這是預期的。啟動失敗時看 `journalctl -u agents-lab` 和 `podman logs agents-lab_agent_1`。

### 3.5 驗證

```bash
c="podman compose -f deploy/compose.prod.yaml"
curl -fsS -X POST localhost:8000/sessions -H 'Content-Type: application/json' -d '{"owner": "cli"}'
$c exec agent date
$c exec agent getent hosts miniflux.internal
curl -fsS --max-time 900 -X POST localhost:8000/jobs/daily-tech/run   # 會真的送到 Slack
```

| 檢查 | 通過條件 |
| --- | --- |
| `POST /sessions` | 回傳 `session_id` |
| `date` | 時區是 `CST`（台北時間） |
| `getent hosts` | 印出 Miniflux 的 IP |
| 觸發任務 | 回傳 200 和 `session_id`；Slack 收到訊息，日期是台北時間，文章來自 Miniflux |
| 重開機（只有第一次部署） | `systemctl reboot` 後，`systemctl status agents-lab` 是 `active`，`podman ps` 的 image 仍然是 `:$sha`，`POST /sessions` 正常 |

`POST /sessions` 之後會換成 `GET /healthz`（見 roadmap 階段 6）。自動化時，觸發任務會真的送出通知，只在第一次部署或手動要求時執行。

### 3.6 確認排程

```bash
diff <(crontab -l 2>/dev/null) deploy/crontab && echo "crontab up to date"
```

有差異時，確認 `crontab -l` 裡沒有別的排程，再執行 `crontab deploy/crontab`。任務名稱要和 `config/config.toml` 的 `[jobs.*]` 一致。

### 3.7 標記 latest（筆電）

```bash
docker buildx imagetools create -t ghcr.io/ccchou/agents-lab:latest "ghcr.io/ccchou/agents-lab:$sha"
```

通過條件：`docker buildx imagetools inspect ghcr.io/ccchou/agents-lab:latest` 的 digest 和 `:$sha` 相同。`latest` 只在沒有 `image.env` 時才會用到，例如新的常駐機器。

### 3.8 清理

```bash
podman image prune -f
```

### 3.9 隔天確認

```bash
tail ~/agent-jobs-*.log
```

通過條件：每個任務都有當天 08:00 的紀錄，而且是 `session_id`，不是 `curl: (22)`。

## 退回舊版

在常駐機器上，用 `~/agent-deploys.log` 裡上一次的 sha：

```bash
git checkout "$prev"
echo "AGENT_IMAGE_TAG=$prev" > /etc/agents-lab/image.env
systemctl daemon-reload
systemctl restart agents-lab
echo "$(date -Iseconds) rollback -> $prev" >> ~/agent-deploys.log
```

再跑一次 3.5。重開機後仍然是 `$prev`，因為版本記在 `image.env`。設定在 3.3 改過時，也要改回來。`latest` 還沒移過去時不用動；已經移過去時，在筆電上把 `latest` 指回 `$prev`（同 3.7）。
