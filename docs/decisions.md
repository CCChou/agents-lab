# 決策紀錄

記錄程式碼讀不出來的設計決策。舊決策不直接修改內容：要推翻時，把狀態改成「已被 D-XXX 取代」，再新增一條。

## D-001：以練習為主，RSS 摘要為實際用途

- 日期：2026-10-31
- 狀態：生效中
- 決定：專案以練習 agent 技術為主，並以 RSS 摘要作為實際用途。每個階段都要同時交付可用功能和一項新技術。
- 原因：純練習缺乏判斷好壞的標準，而摘要是使用者實際需要的功能。
- 考慮過但沒選：純粹做每天使用的工具；純粹練習、沒有實際用途。
- 重新評估的時機：RSS 摘要不再實用，或練習目標改變時。

## D-002：RSS agent 是研究 agent 的雛形

- 日期：2026-10-31
- 狀態：生效中
- 決定：先用 RSS agent 練熟基礎設施，再開始做家庭 agent。
- 原因：RSS agent 唯讀、出錯代價低，可以先驗證共用元件；家庭 agent 涉及個資與有副作用的動作。
- 考慮過但沒選：直接開始做家庭 agent。
- 重新評估的時機：家庭功能的需求變得比摘要更迫切時。

## D-003：架構拆解優先於新功能

- 日期：2026-10-31
- 狀態：生效中，驗證方式已被 D-017 取代
- 決定：階段 0 之後立刻拆解共用元件，目標是新增任意 agent 都很簡單。用 `general` 和 `rss` 兩個 agent 驗證。
- 原因：架構設計是本專案的重點。先拆解，RSS 功能就成為驗證架構的第一個案例。
- 考慮過但沒選：等到第二個 agent 真正出現時才抽象化。
- 重新評估的時機：拆解過程發現抽象不符合實際需求時。

## D-004：以 `Agent` Protocol 作為擴充點

- 日期：2026-10-31
- 狀態：生效中
- 決定：入口只認識 `Agent` 介面。對話型 agent 用 `AgentSpec` + `LoopAgent`，workflow 自行實作 `Agent`。
- 原因：Agent 和 workflow 會並存。統一介面後，入口不用分支，agent-as-tool 也只需要一個轉接器。這裡與 `docs/vision.md` 的「只寫設定」不同，因為 workflow 無法只靠設定完成。
- 考慮過但沒選：只用 `AgentSpec`，無法支援 workflow；把 workflow 包成工具，這樣難以回報進度，也要多花 LLM 判斷的步驟。
- 重新評估的時機：確定不會有 workflow 時，可以移除這層介面。

## D-005：迴圈先不做可恢復

- 日期：2026-10-31
- 狀態：生效中
- 決定：維持同步迴圈，進度不存進對話狀態。
- 原因：初期以 CLI 為主，使用者會當場回覆；目前工具都是唯讀的。之後需要時只影響 `LoopAgent`。
- 考慮過但沒選：現在就做可恢復的結構，因為目前沒有實際需求。
- 重新評估的時機：需要在 LINE 等非同步介面上確認動作時。

## D-006：入口在 agent 外面

- 日期：2026-10-31
- 狀態：生效中
- 決定：CLI、LINE、排程都是 entry adapter，agent 不知道自己如何被觸發或輸出到哪裡。agent 決定要通知，入口負責送出。
- 原因：符合 Clean Architecture，同一個 agent 可以換介面而不改內容。
- 考慮過但沒選：把介面視為 agent 的組成之一。
- 重新評估的時機：無。

## D-007：短期和長期記憶使用不同介面

- 日期：2026-10-31
- 狀態：生效中
- 決定：`ConversationStore` 和 `MemoryStore` 分開，由 `ContextBuilder` 統一組合成 context。兩者可以共用同一個儲存系統。長期記憶也可以包成工具，讓 agent 主動查詢。
- 原因：兩者的存取方式不同：短期依 session 依序讀取，長期依問題搜尋。迴圈只面對 `ContextBuilder`，加入長期記憶時不用改迴圈。LangGraph 也採用類似的分離方式。
- 考慮過但沒選：短期和長期共用一個介面，這樣介面會出現對其中一方沒有意義的方法。
- 重新評估的時機：實作長期記憶時，發現兩個介面有大量重複。

## D-008：訊息內容改成區塊，只保存檔案參照

- 日期：2026-10-31
- 狀態：生效中
- 決定：`Message.content` 改成 `ContentPart` 區塊，階段 1 只實作 `TextPart`。圖片等檔案以參照保存，內容放在 `BlobStore`。
- 原因：`Message` 幾乎每個元件都會用到，趁拆解時修改成本最低。迴圈每輪都會重送訊息，直接保存檔案內容會讓對話紀錄膨脹。
- 考慮過但沒選：維持字串，等需要多模態時再改。
- 重新評估的時機：要支援即時語音對話時，串流與延遲需求需要另外設計。

## D-009：`ToolRegistry` 放在 use_cases

- 日期：2026-10-31
- 狀態：生效中
- 決定：`AgentSpec` 只列工具名稱，由 use_cases 層的 `ToolRegistry` 查找。
- 原因：它只是查表邏輯，不對接外部系統。
- 考慮過但沒選：無。
- 重新評估的時機：工具來源變複雜時，例如接入 MCP。

## D-010：由組裝層依 `AgentSpec` 建立 `LLMClient`

- 日期：2026-10-31
- 狀態：生效中
- 決定：`AgentSpec` 指定模型，組裝層建立對應的 client，`LLMClient` 介面維持不變。
- 原因：每個 agent 可以用不同模型，而不用修改介面。
- 考慮過但沒選：讓 `LLMClient.stream()` 接收 model 參數。
- 重新評估的時機：同一個 agent 要在執行中切換模型時。

## D-011：`Policy` 延後到有副作用的工具出現時

- 日期：2026-10-31
- 狀態：生效中
- 決定：階段 1 不實作 `Policy`。第一個有副作用的工具出現時才加，並先用 CLI 同步確認。
- 原因：目前工具都是唯讀的，不需要確認機制。
- 考慮過但沒選：階段 1 先做一律允許的 `Policy`。
- 重新評估的時機：新增第一個有副作用的工具時。

## D-012：維持手刻工具迴圈

- 日期：2026-10-31
- 狀態：生效中
- 決定：繼續手刻迴圈，LangChain 只用於模型呼叫，不改用 LangGraph 等框架。這與 `docs/vision.md` 的起步建議不同。
- 原因：迴圈本身就是練習內容。
- 考慮過但沒選：Claude Agent SDK、LangGraph、OpenAI Agents SDK。
- 重新評估的時機：階段 5 實作持久化和確認流程時，再評估 LangGraph 的 checkpoint 是否值得採用。

## D-013：Router 和 MCP 延後

- 日期：2026-10-31
- 狀態：生效中
- 決定：每個 agent 先用獨立入口，例如 CLI 的 `--agent`；工具先用自己的 `Tool` Protocol。
- 原因：家人和自己會用不同入口，目前不需要 router。`Tool` Protocol 已經夠用，之後可以用 adapter 接入 MCP，核心不用改。
- 考慮過但沒選：依 `docs/vision.md` 一開始就加入 router 和 MCP。
- 重新評估的時機：多個 agent 要共用同一入口時加 router；要重用外部工具時加 MCP。

## D-014：達到工具上限時，再要求 LLM 回答一次

- 日期：2026-10-31
- 狀態：生效中
- 決定：為未執行的工具呼叫補上結果，再以不提供工具的方式呼叫 LLM 一次。呼叫失敗或回覆為空時，顯示上限訊息。硬上限繼續保留，作為最後一道保險。
- 原因：使用者已經等待多輪，部分答案比錯誤訊息有用。指示放在工具結果裡，不用在對話中途插入 system 訊息。
- 考慮過但沒選：補上工具結果後直接停下，這樣前面查到的資訊都浪費了。
- 重新評估的時機：實際使用的 LLM 服務普遍拒絕這種請求，或部分答案品質太差時。

## D-015：CLI 逐字顯示純文字

- 日期：2026-10-31
- 狀態：已被 D-026 取代
- 決定：`Chat` 即時輸出 `Event`，CLI 收到文字就寫出，不渲染 Markdown，並移除 `rich`。工具通知的文字也由 CLI 決定。
- 原因：等回覆完成才顯示的體驗很差。顯示方式屬於介面，use case 不應受它影響。
- 考慮過但沒選：CLI 收齊後再渲染 Markdown，回覆完成前看不到文字；用 `rich.Live` 邊收邊重繪，CLI 較複雜也較難測試。
- 重新評估的時機：純文字的 Markdown 符號影響閱讀時，可以只改 CLI，改用 `rich.Live`。

## D-016：一輪對話完成後才寫入 `ConversationStore`

- 日期：2026-10-31
- 狀態：生效中
- 決定：一輪對話的訊息先放在記憶體，成功結束才一次寫入。LLM 呼叫失敗時，這一輪全部捨棄。System prompt 不存入對話，每次呼叫時才加上。
- 原因：失敗的訊息不會留在歷史裡，重送時不會重複，歷史也不會處於不完整的狀態。System prompt 屬於 agent 定義，不是對話內容。
- 考慮過但沒選：每則訊息都立即寫入，失敗時要處理不完整的歷史。
- 重新評估的時機：出現有副作用的工具時，捨棄這一輪再重送會重複執行工具；做可恢復的迴圈時也要一併重新設計（見 D-005）。

## D-017：先只做 `rss` agent

- 日期：2026-10-31
- 狀態：生效中
- 決定：`agent/agents/` 只有 `rss`，不做 `general` 和 `--agent`，`__main__.py` 直接組裝 `rss`。`AGENT_SYSTEM_PROMPT` 保留，有設定時覆蓋 `rss` 的預設指令。Miniflux 設定改為必填。
- 原因：目前只需要一個 agent，選擇機制沒有用途。原本移除 `AGENT_SYSTEM_PROMPT` 的理由是有多個 agent，現在不成立。
- 考慮過但沒選：同時做 `general` 和 `--agent`。代價是「新增 agent 不需要改 runtime」這件事還沒有實際驗證。
- 重新評估的時機：出現第二個 agent 時，要加入選擇機制，並確認沒有動到 runtime。

## D-018：用工具提供目前時間

- 日期：2026-11-01
- 狀態：生效中
- 決定：新增 `get_current_time` 工具，由各 agent 在 `AgentSpec.tools` 自行選用。回傳精確到秒的 ISO 8601 時間和星期，時區使用執行環境的時區。先只靠工具的 `description` 引導模型呼叫，不改 `rss` 的 system prompt。
- 原因：不是每個 agent 都需要日期，寫進共用的 system prompt 會讓不需要的 agent 也帶著它，而使用者是否會問到日期也無法事先判斷。工具讓每個 agent 自己決定。
- 考慮過但沒選：由 `ContextBuilder` 加進 system prompt，所有 agent 都會帶到；組裝時寫進 `AgentSpec`，對話跨日後會過期；附在使用者訊息裡，舊日期會留在歷史裡。
- 重新評估的時機：模型實際使用時不呼叫工具、自己猜日期時，再加 system prompt 指示。工具數量變多、工具定義開始佔掉明顯的 context 時，評估拆成 MCP 或 skill，或改成按需載入（MCP 本身不會減少 context，見 D-013）。使用者時區與執行環境不同時，要另外設定時區（例如階段 6 的常駐程序）。

## D-019：由 agent 按需讀取全文

- 日期：2026-11-01
- 狀態：生效中
- 決定：不開 Miniflux 的 crawler。`miniflux_get_entry` 讀取 Miniflux 保存的內文，內文只有摘要時，由 agent 用 `fetch_page` 讀原始網頁。讀網頁的工具放在獨立 adapter，不屬於 Miniflux。HTML 轉換只在 adapter 裡做，domain 只看到字串。
- 原因：17 個 feed 中有 9 個只提供摘要，需要讀原始網頁；crawler 會為每篇新文章抓全文，包含不會讀的文章。按需讀取只抓用得到的內容，`fetch_page` 也能給之後的搜尋 agent 重用。
- 考慮過但沒選：開 crawler，資料量大、舊文章不受影響，也無法給搜尋 agent 用；只做 `miniflux_get_entry`，摘要型 feed 無法讀全文。
- 重新評估的時機：`fetch_page` 常被網站擋下，或需要 JavaScript 才能讀取時。

## D-020：限制工具結果佔用的 context

- 日期：2026-11-01
- 狀態：生效中，列表上限已被 D-022 取代
- 決定：文章列表最多 50 筆。單次讀取內容最多 8,000 字元，超過時標明總長度，模型可用 `offset` 讀下一段。送給 LLM 時，只保留最近一輪的工具結果內容，更早的換成佔位文字；`ConversationStore` 保留完整內容。這部分從階段 3 提前到階段 2，token 計算和 `DigestAgent` 仍在階段 3。
- 原因：工具結果存進歷史後，每次 LLM 呼叫都會重送，有了讀全文的工具後會馬上累積。模型需要時可以重新呼叫工具。佔位文字保留工具呼叫的訊息，工具呼叫和結果才配得起來。
- 考慮過但沒選：等到階段 3 才修剪，長對話會很快撐大 context；把上限設得更低，常見的長文要讀更多次。
- 重新評估的時機：階段 3 有 token 計算後，改用 token 而不是字元。使用者常追問更早一輪的內容，導致模型一直重新讀取時，放寬保留範圍。

## D-021：工具結果標記不可信內容

- 日期：2026-11-01
- 狀態：生效中
- 決定：文章內文和網頁內容包在 `<untrusted_content>` 裡，並在工具結果中註明它只是資料，內容裡的邊界標記要先處理掉。文章標題目前沒有包住。`fetch_page` 只接受 http 和 https，連線前解析主機，只要有一個位址不是公開位址就拒絕，每次重導向都重新檢查。`rss` 的 system prompt 限定只讀文章或使用者提供的網址。
- 原因：註明放在工具結果裡，換掉 `AGENT_SYSTEM_PROMPT` 時也有效。`fetch_page` 由模型決定網址，不擋內部位址就可能讀到區網服務，例如 Miniflux。
- 考慮過但沒選：只寫在 system prompt，會被覆蓋；完全不限制網址，模型可能被文章內容誘導去讀內部服務。
- 重新評估的時機：出現有副作用的工具或長期記憶時（見 D-011）。檢查和連線之間 DNS 可能改變，這個漏洞目前沒有處理，暴露範圍擴大時要改成連線時檢查。

## D-022：用 `summarize_entry` 工具逐篇摘要

- 日期：2026-11-01
- 狀態：生效中，列表上限已被 D-027 取代
- 決定：新增 `summarize_entry` 工具，每篇文章用獨立的 LLM 請求摘要，主對話只收到短摘要。工具放在 use_cases，透過 `ArticleReader` 和 `LLMClient` 兩個 port 工作。Miniflux 內文太短時，由 `ArticleReader` 改讀原文。單篇輸入最多 4,000 字元，摘要請求不提供工具。文章列表上限從 50 調低到 20，由程式強制。
- 原因：多篇全文放進同一個請求會超過模型服務的額度（5 篇約 22,000 token，上限 7,000）。模型不一定遵守 system prompt 的筆數指示，所以上限要由程式強制。工具留在現有對話裡就能用，不需要先做選擇 agent 的機制。
- 考慮過但沒選：換模型服務或升級方案，要付費；一次只讀 1 篇，多篇摘要的需求做不到；提前做 `DigestAgent`，要先加入選擇機制，留給階段 3 的大量摘要。
- 重新評估的時機：階段 3 有 token 計算後，改用 token 計算輸入上限。需要固定流程或幾十篇的摘要時，改用 `DigestAgent`。換到額度較高的模型服務時，重新評估是否還需要逐篇摘要。

## D-023：維持 Chat Completions，用 `reasoning_effort` 接上 `gpt-6-luna`

- 日期：2026-11-02
- 狀態：生效中
- 決定：繼續使用 Chat Completions，新增選填的 `AGENT_LLM_REASONING_EFFORT`，有設定時才送出。`gpt-6-luna` 要設成 `none`。
- 原因：`gpt-6-luna` 在 Chat Completions 上，只有 `reasoning_effort` 為 `none` 時才能用 function tools。Responses API 主要是 OpenAI 的介面，其他模型服務可能只有 Chat Completions，維持現狀才能繼續支援 OpenAI 相容服務。這個 agent 主要是查文章和摘要，不一定需要 reasoning，選填設定的改動最小，也不影響其他服務。
- 考慮過但沒選：改走 Responses API 但不回傳 reasoning item，要改 adapter，卻無法跨工具呼叫延續 reasoning；改走 Responses API 並回傳 reasoning item，要在 `Message` 和 `LLMClient` 加入供應商專屬的狀態。
- 重新評估的時機：工具選擇或摘要品質因為沒有 reasoning 而明顯不足時，直接評估回傳 reasoning item 的做法，並要維持無狀態，不用 `previous_response_id`，避免繞過 D-016 和 D-020。

## D-024：依 category 開頭查詢，先看標題再決定是否讀內文

- 日期：2026-11-02
- 狀態：生效中，筆數上限、列表上限和趨勢的做法已被 D-025、D-027 取代
- 決定：`miniflux_query_entries` 新增 `category_name`，不分大小寫比對 category 名稱的開頭，不能和 `feed_name` 同時使用。比對到多個 category 時分別查詢，再輪流合併，總數上限維持 20 篇（見 D-022）。查詢結果顯示 category 和符合條件的總篇數。新增 `miniflux_list_categories` 工具。`rss` 的 system prompt 要求列文章時只列標題；摘要多篇時先依標題挑選，一次最多 5 篇，並在同一次回覆裡一起呼叫 `summarize_entry`。使用者提到主題或類別時，先確認有沒有對應的 category，有就用 `category_name`，沒有才用 `search`。工具說明只寫共用的用法和成本；「新聞」、「科技」對應的 category 前綴、筆數上限和回覆流程寫在 `rss` 的 system prompt。
- 原因：使用者的 category 以 `News`、`Tech` 分組，要能一次查整組。比對「包含」時，`it` 也會比對到 `Tech - Architecture`。單純依時間合併時，發文頻率高或剛更新的 category 會佔滿名額：實測今天 112 篇未讀新聞的前 5 篇有 4 篇來自 `News - IT`，前 20 篇完全沒有 `News - World`。查詢結果本來就不含內文，先看標題可以用很少的 token 過濾不需要的文章。總篇數讓模型能回報還有幾篇沒處理。實測時只靠工具的 `description`，模型問「AI 的文章」會直接用 `search`，混進不相關的文章，所以這裡不沿用 D-018 先不改 system prompt 的做法。
- 考慮過但沒選：依發布時間合併，類別分布太偏；沿用 `feed_name` 的「包含」比對，容易誤中；Miniflux 的 `category_id` 參數，一次只能指定一個 category；不改 system prompt，模型沒有先挑選的指示。
- 重新評估的時機：只看標題常漏掉好文章時。要涵蓋整個 category 而不是挑 5 篇時，改用 `DigestAgent`（階段 3），重用 `category_name` 的比對邏輯。工具結果的標題仍未標記為不可信內容，出現有副作用的工具前要處理（見 D-021）。

## D-025：由程式強制單一工具的每輪上限，回覆標示來源和查證程度

- 日期：2026-11-02
- 狀態：生效中，趨勢是否讀內文已被 D-027 取代
- 決定：`AgentSpec` 新增 `tool_call_limits`，以工具名稱設定一輪對話的呼叫上限，由 `LoopAgent` 計數。超過時不執行、不輸出 `ToolStarted`，改回傳未執行的工具結果。`rss` 設定 `summarize_entry` 一輪最多 5 次，prompt 使用同一個常數。使用 `category_name` 時，查詢結果列出每個 category 的顯示數和總數，沒有文章也會列出。模型依重要度從標題挑選要讀的文章，趨勢的每一列標示「已讀內容」或「僅標題」，回覆使用固定區塊。
- 原因：只寫在 prompt 的 5 篇上限沒有被遵守，實測模型嘗試摘要 20 篇，14 篇成功，至少 4 篇撞到工具上限。`max_tool_iterations` 計算 LLM 回合，擋不住同一次回覆裡的多個呼叫。上限放在 `LoopAgent`，新工具不用各自計數，工具本身也不用知道一輪對話的範圍。只看標題容易補上標題沒有的細節，也可能把少量樣本當成趨勢，所以要標示依據並保留有限的查證。來源數量由工具回報，使用者才能判斷有沒有漏。
- 考慮過但沒選：只靠 prompt，已實測無法保證；在 `SummarizeEntryTool` 裡計數，工具不知道一輪對話的邊界；趨勢完全只看標題，容易產生幻覺；來源由模型自己整理，漏掉時看不出來。
- 重新評估的時機：階段 3 的 `DigestAgent` 能涵蓋整個 category 時，重新評估這條路徑是否還要做趨勢。階段 4 有 eval 後，用資料確認查證標示和幻覺比例。回覆格式造成 token 或閱讀負擔時再精簡。

## D-026：終端機互動時用 `prompt_toolkit` 輸入，用 `rich` 分段渲染 Markdown

- 日期：2026-11-02
- 狀態：生效中
- 決定：標準輸入和輸出都是終端機時，輸入改用 `prompt_toolkit`，輸出由 `MarkdownBlockWriter` 累積文字，遇到空行才用 `rich` 渲染完成的區塊。工具通知和錯誤訊息出現前，會先印出累積的文字。其他情況維持一行一行讀取和逐字純文字輸出。
- 原因：`rss` 的回覆有標題和表格，純文字顯示 Markdown 符號不好讀。Python 的 `input()` 在這個環境使用 libedit，中文折行後在中間刪除時重繪位置不正確；程式另外印提示字元時，libedit 也不知道提示字元的寬度。`prompt_toolkit` 在同一情境下重繪正常。分段渲染不用重繪，回覆超過一個畫面時也不影響捲動。
- 考慮過但沒選：`rich.Live`，回覆超過一個畫面時重繪和捲動容易出問題；只把提示字元交給 `input()`，解決不了折行時的雙寬字元問題；維持純文字，表格難讀。
- 重新評估的時機：逐段顯示的等待感太明顯時，再評估只渲染目前畫面的做法。Web UI 或訊息平台出現時，這些都只留在 CLI。虛擬終端無法模擬輸入法組字，組字中的顯示問題要在實際終端機確認。

## D-027：列表上限改為每個 category 15 篇，回合數只當安全網

- 日期：2026-11-02
- 狀態：生效中，一輪的總上限和分別查詢的做法改由 D-032 決定
- 決定：`limit` 上限改成 15，用 `category_name` 時對比對到的每個 category 各自生效，不再限制合併後的總數。新增 `offset` 翻頁，同樣對每個 category 生效，還有文章時工具結果會提示下一個 offset。`rss` 的 `max_tool_iterations` 改成 10，`miniflux_query_entries` 一輪最多 5 次，`summarize_entry` 維持 5 次。看趨勢或總覽預設不讀內文，明確要求摘要或推薦時才讀。使用者只要特定 category 時，用完整名稱在同一次回覆裡分別查詢。
- 原因：20 篇總上限由所有 category 共用，查中東和世界新聞時，61 篇只看到 13 篇。每個 category 要有基本量，趨勢才有足夠的標題可以判斷；模型只讀標題，token 比讀全文少很多。這會讓 D-022 記錄的每分鐘額度問題更容易出現，用額度較低的模型服務時要注意。回合數上限只防失控，真正的控制放在成本較高的工具上，所以 5 輪偏低，查詢次數另外限制，避免模型一直換參數查列表。
- 考慮過但沒選：按 feed 分配，來源最完整，但中新網會佔兩份額度，使用者選擇先按 category；加 60 篇總上限，目前比對到的 category 最多 4 個，不需要；維持 20 篇總上限，涵蓋不足；用查詢次數以外的 token 預算，要等階段 3 有 token 計算。
- 重新評估的時機：同一個 category 裡某個 feed 佔滿名額時，改按 feed 分配。換回額度較低的模型服務時，重新評估列表大小。階段 3 有 token 計算後，評估用 token 預算取代查詢次數。

## D-028：模型服務拒絕無效的工具呼叫時，重試一次

- 日期：2026-11-02
- 狀態：生效中
- 決定：`OpenAICompatibleLLMClient` 收到錯誤訊息包含 `tool call validation failed` 時，用相同的請求重試一次，再失敗就照常丟出錯誤。已經送出文字或工具呼叫後不重試。
- 原因：Groq 會在服務端驗證模型產生的工具呼叫。模型寫錯工具名稱或漏參數時，請求直接失敗，不會進到 `LoopAgent`，所以無法用 D-014 的方式把錯誤交回模型，整輪問答會中斷。這類錯誤來自模型輸出，重新生成通常有機會成功。已送出內容時重試會造成重複輸出。
- 考慮過但沒選：不處理，實測 4 次失敗 3 次；在 `LoopAgent` 重試，錯誤訊息屬於模型服務的細節，應該留在 adapter；多次重試，每次都是一個 LLM 請求，失敗時也要等更久。
- 重新評估的時機：重試後仍常失敗時，評估換模型或減少工具數量。其他模型服務使用不同的錯誤訊息時，再擴充判斷條件。

## D-029：工具去除同標題文章，category 對照寫在 system prompt

- 日期：2026-11-02
- 狀態：生效中
- 決定：`miniflux_query_entries` 在每次查詢的結果裡，以去除空白、忽略大小寫後的標題去重，保留先出現的一筆，並回報隱藏篇數。翻頁時，顯示數包含前面的頁面。`rss` 的 system prompt 列出全部 category 和關鍵字，使用者指定或排除 category 時，只查符合的 category。標題列表預設不列，只有列文章或使用者要求時才列。
- 原因：今天 153 篇 news 有 8 組同標題，來源是 feed 本身：BBC 同一網址有兩筆，中新網會用不同網址重新發布。模型逐頁自己累加顯示數時算錯，由工具回報比較可靠。關鍵字對照能減少模型先查整個 `News` 的情況，也不用多呼叫一次 `miniflux_list_categories`。查詢範圍已經能判斷有沒有漏，長標題清單只會把重點推到後面。
- 考慮過但沒選：用網址去重，抓不到中新網重新發布的文章；讓工具記住前幾頁來跨頁去重，工具要多保存狀態；由模型合併同一事件的不同標題，留給 `DigestAgent`；把對照表抽成 skill，目前沒有載入 skill 的機制，這份資料每次查詢都用得到，放在 prompt 也只多幾行。
- 重新評估的時機：`total` 含重複文章而影響判斷時。跨頁重複常出現時。Category 常變動時，把對照表移到設定檔，或在啟動時讀取 Miniflux 的 category，只把關鍵字留在設定裡。Agent 出現多種需要按需載入的流程時，再評估 skill。

## D-030：趨勢先從所有標題歸納，摘要只用來查證

- 日期：2026-11-02
- 狀態：生效中，標題總量改由 D-032 決定
- 決定：看趨勢時，先依標題的出現次數和影響範圍歸納議題，沒有摘要的議題也要列出並標示「僅標題」。摘要只用來查證最重要的議題和挑選推薦。重要度欄只寫高、中高、中、低，理由寫在表格下方。
- 原因：實測 30 篇標題裡有多篇美國期中選舉，但趨勢表只有 5 列，每列對應一篇摘要，這個議題完全消失。重要度欄寫入理由時，終端機的表格會截斷內容。
- 考慮過但沒選：看趨勢時固定翻到第二頁，查特定 category 和查整個 `News` 的規則會不一致，也沒有解決只依摘要歸納的問題。
- 重新評估的時機：30 篇標題仍不夠時，評估一次查詢多個 category 的固定標題預算，例如 60 篇平均分配，不用為不同範圍寫特例。

## D-031：用溫度和明確規則降低回覆差異，固定流程留給 workflow

- 日期：2026-11-02
- 狀態：生效中，摘要時機改為查詢完成後（見 D-032）
- 決定：新增選填的 `AGENT_LLM_TEMPERATURE`，有設定時才送出。`rss` 的 prompt 限定查證欄只能寫三種標籤，規定翻頁完成後才能摘要，回覆不使用粗體。議題排序、用字和選文接受每次不同；流程順序、數字和標籤要一致。
- 原因：同一個問題實測兩次，流程順序、讀內容篇數和查證標籤都不同。`LoopAgent` 由模型決定流程，這是預期內的差異，但不需要判斷的部分不該有差異。Markdown 的 `**` 緊接中文標點時可能不會變成粗體，終端機會顯示原始符號。
- 考慮過但沒選：繼續增加 prompt 規則，規則已經很多，模型不一定全部遵守；現在就做趨勢 workflow，範圍較大，先用小調整確認效果。
- 重新評估的時機：小調整後流程和數字仍不穩定時，把「查詢範圍」改由程式統計。需要固定的趨勢分析流程時，和 `DigestAgent` 一起做成 workflow（見 D-004）。

## D-032：回答一個問題最多看 60 篇標題，先用 prompt 的軟上限

- 日期：2026-11-02
- 狀態：生效中
- 決定：`rss` 的 prompt 規定回答一個問題時，所有查詢顯示的標題加起來最多 60 篇。模型先依各 category 的總數（見 D-033）和相關度，用一行寫出查詢計畫，再依計畫在同一次回覆裡呼叫全部查詢，完成後就不再查，分配用不完也不重新分配。標題不足不再是翻頁的理由，要看更多由使用者提出，重新規劃並用 `offset` 接續。Prompt 不寫單次查詢的篇數：單次 15 篇是 `miniflux_query_entries` 的硬上限，用來控制回應大小，寫在工具參數說明。程式不強制總量；查詢次數維持 D-027 的一輪 5 次，並寫進 prompt，讓計畫不會超過。這個決定補上 D-027 當時沒選的總上限。
- 原因：D-027 認為比對到的 category 不多，不需要總上限，但沒有算到翻頁會累加，實測翻到 61 篇。工具每次呼叫都獨立，不知道這一輪查過多少篇，要精準限制就得改工具介面或 `LoopAgent`，所以先用 prompt 看效果。只寫總量規則時，實測回報 82 篇：工具結果提示還有文章會引導翻頁，一起送出的查詢也無法中途停止，所以改成查詢前先規劃，總量和 `offset` 都事先決定。
- 考慮過但沒選：工具一次接受多個 category 並寫出分配，單次總量由工具限制，同一範圍很精準，但要改工具參數和 15 篇的單次上限，使用者決定先不動工具；工具回報篇數，由 `LoopAgent` 累計，一輪內完全精準，但要改所有工具共用的介面；替整個 `Tech` 另訂較小的 `limit`，這是特例，模型自己分配時也能選較小的值。
- 重新評估的時機：先規劃後，實測模型仍常超過 60 篇時，改用工具接受多個 category 的做法（見 D-030）。

## D-033：用獨立工具計算各 category 的篇數

- 日期：2026-11-02
- 狀態：生效中
- 決定：新增 `miniflux_count_entries_by_category`，傳入 category 名稱清單，可選讀取狀態和發布時間範圍，回傳各 category 的篇數和總數。名稱比對規則和 `category_name` 相同，重疊的 category 只算一次。工具內部對每個 category 查一次 `total`，只處理傳入的 category。`miniflux_list_categories` 維持列出所有名稱，用途分開。這個工具不佔 `miniflux_query_entries` 的查詢額度。
- 原因：模型規劃分配（見 D-032）前要知道篇數，但 `miniflux_list_categories` 只有未讀數，不受時間範圍影響，Miniflux 也沒有依時間範圍回傳各 category 篇數的 API。讀取狀態要和查詢條件一致，否則問未讀文章時會分配到不存在的篇數。
- 考慮過但沒選：用 `limit` 1 的查詢探查總數，不用新工具，但模型會逐一探查，把查詢額度用完；讓 `miniflux_list_categories` 接受時間範圍，一次列出全部，category 多時請求數也跟著變多。
- 重新評估的時機：Category 數量多到計數明顯變慢時，改成並行請求或快取。

## D-034：Session 生命週期由 `SessionManager` 管理，`/reset` 開新 session

- 日期：2026-11-06
- 狀態：生效中
- 決定：新增 `SessionRegistry` 介面，記住每個 owner 目前用哪個 session；新增 use case `SessionManager`，提供 `current_or_start` 和 `start_new`。`ConversationStore`（內容角色）和 `SessionRegistry`（生命週期角色）是同一個 Session 概念，介面依使用者分開，由同一個 adapter 實作，`InMemoryConversationStore` 因此改名為 `InMemorySessionStore`。入口不再自己決定 session id，只提供 owner（CLI 為 `cli`），並解析指令文字。`/reset` 開一個新的 session，舊的訊息保留，只是不再送給模型。需要同時處理兩個角色的操作（resume、clear、列出 session）以後都放在 `SessionManager`。
- 原因：開新對話和刪除歷史是不同的操作，業界常見的做法也分開：LangGraph 換 `thread_id` 開新對話，用 `delete_thread` 刪除；Google ADK 由 SessionService 管理生命週期。以後的 resume、clear、持久化都會同時碰到 session 清單和訊息，放在同一個協調者和同一個 adapter，才能保持一致，也能用同一個 transaction。介面分開，`LoopAgent` 只看到 `load` 和 `append`，不需要知道 reset。LINE 這類 owner id 固定的入口可以重用同一個 `SessionManager`。
- 考慮過但沒選：CLI 自己換 session id，改動最少，但生命週期散在各個入口，resume 和 clear 沒有位置；在 `ConversationStore` 加 `clear()`，把開新對話和刪除混在一起，也無法 resume；`Agent` 加 `reset()`，每種 agent 都要實作，違反單一職責；合併成一個 `SessionRepository` 大介面，`LoopAgent` 會依賴用不到的方法；在同一個 session 的紀錄裡寫入重置事件（Rasa 的 `Restarted`），讀取時要找最後一個重置點；另外加一層入口 use case 統一解析指令，目前只有 CLI 一個入口，太早。
- 重新評估的時機：加入 LINE 等第二個入口時，把指令解析和協調移到共用的 use case；需要刪除歷史時，`ConversationStore` 加 `delete`，由 `SessionManager.clear` 呼叫；做 `/resume` 或列出 session 時，`SessionRegistry` 要記住 owner 的所有 session，不只目前的那一個。目前 CLI 直接依賴 `SessionManager` 類別；出現第二種 session 生命週期的實作，或入口測試需要模擬 `SessionManager` 時，在 domain 加 `SessionLifecycle` 輸入介面，和 `Agent` 的做法一致。`SessionLifecycle` 已在 D-035 因 `RemoteSessions` 加入。

## D-035：CLI 和 Web 都透過常駐服務對話，HTTP 邊界用自己的 DTO，串流用 SSE

- 日期：2026-11-08
- 狀態：生效中
- 決定：新增 `python -m agent serve` 常駐服務，用 FastAPI 提供 `POST /sessions`（以 `SessionManager.start_new(owner)` 開 session，回傳 `session_id`）和 `POST /sessions/{id}/messages`（以 SSE 回傳事件串流）。服務是 session 和對話的唯一事實來源，不做驗證，預設只綁定 `127.0.0.1`；`serve --host` 可以改成其他位址，例如 container 裡的 `0.0.0.0`，這時服務只能在內網使用，接受內網裡任何人都能對話和觸發任務的風險。送出訊息只回傳 SSE，不另外提供完整的 JSON 回應。HTTP 邊界在 `agent/adapters/http/wire.py` 定義自己的傳輸 DTO（Pydantic），每個事件帶 `type` 欄位，由對應函式和 domain 的 `Event` 互相轉換；domain 的 `Event` 維持原樣。`turn_completed` 和 `turn_failed` 只存在於傳輸層，因為經過網路後失敗無法再用例外表示。服務端和客戶端共用 `wire.py`。endpoint 只負責轉換和呼叫 `Agent.run()`。客戶端中斷連線時停止執行，這一輪不保存（同 D-016）。CLI 新增客戶端模式 `python -m agent chat --server <url>`：`RemoteAgent` 實作 `Agent`，把 SSE 還原成 `Event`，收到 `turn_failed` 時丟出例外；`RemoteSessions` 透過 API 開 session。domain 新增 `SessionLifecycle` 介面（`current_or_start`、`start_new`），由 `SessionManager` 和 `RemoteSessions` 實作，`cli.run` 改為依賴這個介面。原本同一個程序的 CLI 模式（`python -m agent`）保留。Web 之後也透過同一套 API 對話，owner 分別是 `cli` 和 `web`。
- 原因：互動方式只有 CLI 和 Web，兩者要看到同一份 session，狀態必須集中在一個服務。這和 OpenClaw 的 Gateway、Hermes Agent 多種模式共用同一個核心的做法相同。新的入口只是另一個 adapter，`LoopAgent`、`ContextBuilder` 和 domain 都不用改；CLI 原本就只依賴 `Agent`，換成 `RemoteAgent` 後畫面和錯誤處理都能沿用。傳輸 DTO 和 domain 分開，domain 可以自由重構而不影響客戶端，也和 `_to_langchain_message`、Miniflux adapter 在其他邊界的做法一致；同一個程序裡的各層直接用 domain 的型別，不另外定義 DTO。`Event` 是單向的事件串流，ChatGPT、Claude API 和 A2A 的文字串流也都用 SSE；SSE 是一般的 HTTP，重連是內建的，TUI 用 `httpx` 就能讀。目前不需要在執行中途向客戶端要求權限（D-005 維持原樣），所以不需要雙向的傳輸。保留同一個程序的 CLI 模式，開發和除錯時不用先啟動服務。
- 考慮過但沒選：WebSocket，雙向但要自己處理重連、心跳和訊息編號，目前用不到；直接用 `dataclasses.asdict` 序列化 domain 的型別，沒有型別標記，domain 的命名也會變成對外契約；送出訊息同時提供 JSON 和 SSE，現在沒有不需要串流的客戶端；客戶端另外定義一份 DTO，服務端和客戶端都在 adapter 層，共用不違反依賴規則；CLI 只保留客戶端模式，開發時每次都要先啟動服務；由服務負責排程並推送到 Slack 等通知通道，通知的設計還沒確定，先不做。
- 重新評估的時機：服務要從內網以外連到時，例如 Ingress 或公開的網址，先加上驗證或透過 Tailscale、SSH tunnel；執行中途需要向客戶端要求確認（`Policy`、D-005）時，先試「SSE 送出需要輸入的事件，客戶端用新的請求回答」，不夠時再換 WebSocket；服務需要在沒有請求時主動推送時，改用 WebSocket；服務重啟後 session 會遺失，需要保留時做持久化（階段 5）；Web 改用 TypeScript 等其他語言時，由 Pydantic 產生 JSON Schema 給客戶端。

## D-036：Session 由 `SessionManager` 依時間和數量回收

- 日期：2026-11-08
- 狀態：生效中
- 決定：`SessionManager` 在每次 `start_new` 開新 session 後執行回收，依 owner 套用 `RetentionRule`（`owner_prefix`、`max_age`、`keep_last`）：超過 `max_age` 或不在最新 `keep_last` 個以內的 session 都刪除，兩條規則符合任一條就刪。每個 owner 目前的 session 永遠不刪。預設規則在組裝時設定：`job:` 保留 7 天、最多 7 個；其他 owner 保留 7 天，不限數量。`SessionRegistry` 新增 `sessions(owner_id)`（回傳 session id 和建立時間）和 `remove(owner_id, session_id)`，`ConversationStore` 新增 `delete(session_id)`，`InMemorySessionStore` 同時實作這些方法。時間由注入的 clock 取得。回收不定期執行，只在開新 session 時觸發，每次檢查所有 owner；沒有人開新 session 時，過期的 session 會留到下一次觸發才刪除，所以「保留 7 天」是「下一次觸發時刪除超過 7 天的」，不保證準時。沒有新 session 時資料也不會增加，用來控制記憶體已經足夠；每日排程任務上線後，等於每天至少觸發一次。
- 原因：`serve` 是常駐服務，資料雖然只存在記憶體，重啟前仍會一直累積；每次排程任務都會開一個 session，`ConversationStore` 又保存完整的工具結果（D-020），累積得更快。回收屬於 session 生命週期，放在 `SessionManager`（D-034），儲存那一側只提供列出和刪除。依數量回收適合排程任務，舊的摘要沒有追問的價值；依時間回收適用於所有 owner。在 `start_new` 時順便執行，不需要另外的排程。目前的 session 不刪，避免正在進行的對話被刪除。
- 考慮過但沒選：不回收，等持久化再處理，常駐服務在重啟前會一直累積；只依時間，任務的 session 在期限內仍會累積；只依數量，很少開新 session 的 owner 會一直保留舊資料；任務送出通知後立即刪除 session，以後就無法追問；用 timer 呼叫獨立的回收 endpoint，目前資料量小，不需要額外的排程。
- 重新評估的時機：需要保證準時刪除時（例如隱私的考量），新增 `POST /maintenance/prune`，由 systemd timer 定期呼叫 `prune()`；資料量變大、回收讓 `start_new` 明顯變慢時，同樣改用 timer 定期回收；做持久化（階段 5）時，`SqliteSessionStore` 要實作同樣的方法，並把列出和刪除放在同一個 transaction；多個客戶端共用同一個 owner 時，非目前的 session 可能在使用中被刪除，被刪除的 session 在這一輪結束時會被寫回成孤兒資料，需要時再加上使用中的標記；需要依使用者調整規則時，改從設定檔讀取。

## D-037：排程任務由 `RunJob` 交付，agent 只產生內容

- 日期：2026-11-08
- 狀態：生效中
- 決定：新增 use case `RunJob`：依名稱從 `JobSource` 取得 `Job`（`name`、`prompt`、`channels`），以 owner `job:{name}` 開新 session，呼叫 `Agent.run()`，把 `TextDelta` 接成完整的 Markdown，再交給 `job.channels` 列出的每個 `Notifier`；agent 失敗時改送錯誤通知。`Notification` 包含 `title`、`markdown` 和 `session_id`，`session_id` 目前不顯示在通知裡，等有 `resume` 再用。`Notifier` 和 `JobSource` 是 domain 介面，第一個實作是 `SlackWebhookNotifier`（在 adapter 裡把 Markdown 轉成 Slack 的 mrkdwn，表格轉成列表）和 `TomlJobSource`。任務定義放在設定檔的 `[jobs.<name>]`（D-038），`TomlJobSource` 每次執行都重新讀取，修改任務不用重啟；任務是選用的，設定檔沒有 `[jobs]` 時 endpoint 仍然存在，觸發時回傳 404。webhook 網址由環境變數 `SLACK_WEBHOOK_URL` 指定。HTTP API 新增 `POST /jobs/{name}/run`，等任務完成才回應：成功回傳 200 和 `session_id`，agent 失敗但錯誤通知已送出回傳 502，通知送不出去回傳 500，找不到任務回傳 404。觸發由服務外部的排程器用 `curl` 呼叫這個 endpoint，服務本身不負責排程；目前用服務所在機器的 cron，範例在 `deploy/crontab.example`（D-039），改成 k8s 後換成 CronJob。互動仍只透過 CLI 和 Web，通知是單向的，追問時回到對話中進行。
- 原因：每天送出摘要是一定要做到的事，不能交給模型決定（同 D-025）。agent 有送出訊息的工具時，文章內容可能誘導它把資料送到其他地方，風險比 `fetch_page` 更高（D-021）。產生內容和交付分開後，CLI 可以用同一個 agent 而不會送出通知；`RunJob` 只依賴 `Agent` 介面，以後把 `LoopAgent` 換成每日摘要的 workflow（D-031），交付不用改。輸出要送到哪裡由呼叫者決定，跟 CLI 把事件印到終端機相同。呈現格式在 adapter 裡轉換，模型一律輸出 Markdown（同 D-026）。時間交給外部的排程器，服務不用處理重啟、補跑和重複執行；任務定義、執行和格式轉換放在專案裡，才能測試。等任務完成才回應，排程器能從 `curl` 的結束代碼判斷成功或失敗。
- 考慮過但沒選：agent 用工具送出通知，不保證每次都送，還有副作用和 prompt injection 的風險；送出作為 workflow 的最後一步，內容和交付綁在一起，在 CLI 裡用同一個流程也會送出；外部 script 解析 SSE 並送出，格式轉換沒有測試；服務內建排程器，要自己處理重啟、補跑和重複執行，目前不需要讓 agent 管理排程；HTTP endpoint 自己協調 agent 和通知，交付的規則會放在 adapter 裡；Slack 互動式 bot，互動只透過 CLI 和 Web；任務定義進版控，prompt 的變更有紀錄，但任務和通道是每台機器的設定；systemd timer，錯過時可以補跑、記錄在 journald，也做過所有任務共用的 `agent-job@.service` 範本，但改成 container 部署（D-039）後服務不再由 systemd 管理，cron 只要一行，寫法也和 k8s CronJob 相近。
- 重新評估的時機：要讓 agent 在對話中管理排程時，改成服務內建排程，並搭配 `Policy` 確認（D-005），任務定義和 `Notifier` 可以沿用；需要依內容判斷要不要通知時，讓模型在回答裡標示，由 `RunJob` 決定，送出仍不交給模型；摘要品質不穩定時，用 workflow 取代 `LoopAgent`；同一個任務可能同時被觸發時，加上執行中的鎖；有 `resume` 後，在通知裡附上追問的方式；Slack 的區塊長度不夠時，切成多則訊息；做 eval 需要追蹤 prompt 版本時，重新考慮把任務定義進版控；想把排程時間和任務寫在一起時，在 `[jobs.<name>]` 加上 `schedule`，改成服務內建排程，多個 replica 時要避免重複觸發。

## D-038：設定集中在一個 TOML 設定檔，密鑰放在環境變數

- 日期：2026-11-10
- 狀態：生效中
- 決定：設定集中在一個 TOML 設定檔，由 `load_config(path, env)` 讀成 `AppConfig`（`llm`、`miniflux`、`slack_webhook_url`、`debug`），任務也放在同一個檔案的 `[jobs]`（D-037）。密鑰 `AGENT_LLM_API_KEY`、`MINIFLUX_API_KEY`、`SLACK_WEBHOOK_URL` 只從環境變數讀，其他設定只從檔案讀，環境變數不能覆蓋檔案。設定檔的路徑由 `--config` 指定，沒有時讀 `AGENT_CONFIG`，兩者都沒有就無法啟動，不在啟動目錄或固定路徑裡找。`serve` 和同一個程序的對話需要設定檔，`chat --server` 不需要。監聽的位址由 `serve --host`、`--port` 決定，不放進設定檔。缺少必填欄位、型別錯誤或缺少密鑰時，啟動時丟出 `ConfigError` 並指出欄位名稱。原本的 `AGENT_LLM_BASE_URL`、`AGENT_LLM_MODEL`、`AGENT_LLM_TEMPERATURE`、`AGENT_LLM_REASONING_EFFORT`、`AGENT_SYSTEM_PROMPT`、`MINIFLUX_BASE_URL`、`MINIFLUX_CA_BUNDLE`、`MINIFLUX_VERIFY_SSL`、`AGENT_DEBUG` 依序改成 `llm.base_url`、`llm.model`、`llm.temperature`、`llm.reasoning_effort`、`llm.system_prompt`、`miniflux.base_url`、`miniflux.ca_bundle`、`miniflux.verify_ssl`、`debug`，`AGENT_JOBS_FILE` 移除，不保留讀環境變數的舊方式。專案只放 `config.example.toml`，設定檔放在 `config/` 目錄，整個目錄加進 `.gitignore`，同一台機器可以放多份設定檔，例如測試用的 `config/test.toml`。
- 原因：之後要用 container 部署，再換成 k8s。設定檔可以整份掛進 container（k8s 的 ConfigMap），密鑰交給 Secret，兩者分開管理。原本 `jobs.toml` 的預設路徑依賴啟動目錄，在 container 裡沒有意義，在主機上換目錄啟動也會找不到。每個設定只有一個來源，查問題時不用比對檔案和環境變數。監聽的位址屬於怎麼啟動程序，container 裡一定是 `0.0.0.0`，寫在啟動指令裡，不依賴掛進來的設定檔（D-035）。env 由參數傳進 `load_config`，測試不用修改程序的環境變數。只有一個使用者，同時維護兩種讀取方式不划算。任務是選用的，設定檔沒有 `[jobs]` 也能啟動，任務有錯時在執行時才報錯。
- 考慮過但沒選：繼續用環境變數，設定多了難管理，`export` 的寫法也不被 `docker run --env-file` 接受；沒有指定時在啟動目錄找設定檔，結果依賴從哪裡啟動；沒有指定時讀 `~/.config/agents-lab/config.toml`，多一個要記的位置；環境變數可以覆蓋任何設定，同一個值有兩個來源；任務留在獨立的 `jobs.toml`，部署時要多掛一個檔案；啟動時檢查 `[jobs]`，任務是選用的功能，不應該讓服務無法啟動；用 `pydantic-settings` 等套件，標準函式庫的 `tomllib` 就夠用。
- 重新評估的時機：dev 和 prod 的設定差很多時，再考慮多個檔案或覆蓋機制；修改其他設定也要不重啟就生效時，整份設定改成每次讀取或監看檔案；欄位多到手寫檢查難以維護時，改用 Pydantic 定義設定的 schema（服務已經依賴 Pydantic）。

## D-039：用 Docker Compose 在單機上以 container 部署，排程交給主機的 cron

- 日期：2026-11-11
- 狀態：生效中
- 決定：`deploy/` 只放 container 部署需要的檔案：`Dockerfile`、`compose.yaml` 和 `crontab.example`，移除 systemd 的範例。image 從專案根目錄建置（`docker build -f deploy/Dockerfile .`），以 `python:3.14-slim` 為基礎，用 uv 依 `uv.lock` 安裝執行需要的套件，用非 root 使用者執行；`CMD` 直接以 Python 執行 `serve --host 0.0.0.0 --port 8000`，不經過 `uv run`。image 裡設定 `AGENT_CONFIG=/etc/agent/config.toml`，並安裝 `tzdata`。根目錄的 `.dockerignore` 用白名單，只放進 `pyproject.toml`、`uv.lock` 和 `agent/`。`compose.yaml` 用 `env_file` 載入密鑰，把專案的 `config/` 目錄唯讀掛到 `/etc/agent/`，設定 `TZ`，只開放 `127.0.0.1:8000`，並設定 `restart: unless-stopped`。設定檔在本機也放在 `config/config.toml`，測試用的設定檔也放在 `config/`，不會進版控。env 檔改成每行一個 `KEY=VALUE`，不寫 `export`、值不加引號，本機用 `set -a; source prod.env; set +a` 載入。排程由主機的 cron 用 `curl -f` 呼叫 `POST /jobs/{name}/run`，輸出附加到記錄檔。只跑一個 container，不寫 k8s manifests。
- 原因：之後要換成 k8s，現在先用 container 部署，image、設定檔目錄、密鑰和排程都能一對一換成 Deployment、ConfigMap、Secret 和 CronJob，程式不用改。Compose 把 port、密鑰、掛載、時區和重啟寫在一個檔案裡，不用在文件裡維護一長串 `docker run`。container 預設是 UTC，`CurrentTimeTool` 回報的時間和「過去 24 小時」都依賴時區，所以要裝 `tzdata` 並設定 `TZ`。掛整個目錄而不是單一檔案：編輯器存檔時常會換成新的檔案，單一檔案的 bind mount 會一直讀到舊內容，修改 `[jobs]` 不用重啟（D-037）就會失效，k8s 的 ConfigMap 用 `subPath` 掛載時也一樣。Python 是 PID 1，`docker stop` 送出的訊號能直接讓 uvicorn 正常結束。白名單式的 `.dockerignore` 確保密鑰和本機設定不會被包進 image。`KEY=VALUE` 在 shell、`docker run --env-file`、compose 和 `kubectl create secret --from-env-file` 都能用，`export` 的寫法不行。cron 在主機上，服務只需要開放給主機；Docker 會直接修改 iptables，ufw 擋不住，開放到區網要在 `compose.yaml` 明確修改。session 只存在記憶體，只能跑一個 container（見 roadmap 的「待決定」）。
- 考慮過但沒選：繼續用 systemd 管理服務和排程，container 部署後服務改由 Docker 重啟，systemd 只剩觸發，cron 一行就夠；服務內建排程，同 D-037；`Dockerfile` 放在根目錄，部署相關的檔案分散在兩個地方；只寫 `docker run` 指令，參數多，也沒有地方記錄部署的設定；`CMD` 用 `uv run`，多一層程序，image 裡也要能解析專案；`.dockerignore` 用黑名單，新增本機檔案時容易漏掉；現在就寫 k8s manifests，沒有叢集可以驗證；用 scheduler container（例如 supercronic）在 compose 裡排程，多一個 container，換成 k8s 時還是要改成 CronJob。
- 重新評估的時機：改用 k8s 時，把 compose 換成 Deployment（`replicas: 1`、`strategy: Recreate`）、Service、ConfigMap（不用 `subPath`）、Secret 和 CronJob，這時 image 要推到 registry，也要重新看 D-035 的驗證；需要健康檢查時，新增 `GET /healthz`，用在 compose 的 `healthcheck` 和 k8s 的 probe；錯過的排程需要補跑時，改用 systemd timer 或 k8s CronJob 的 `startingDeadlineSeconds`；需要從其他機器連到服務時，改 `ports`，並確認仍在內網（D-035）。
