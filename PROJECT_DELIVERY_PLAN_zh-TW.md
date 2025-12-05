# AgentScope Debate Platform — 開發者交付企劃書與維護指南

本文件提供完整的系統概觀、運維與開發指南，作為後續維護與功能擴充的標準參考。內容涵蓋架構、部署、資料模型、API、工作流程（Worker/Celery）、工具集（ToolSet）管理、測試、監控、安全、版本管理與常見問題排除。建議將本文件納入團隊知識庫並持續更新。

---

## 目錄
- 1. 專案簡介與目標
- 2. 系統架構與元件說明
- 3. 本地與容器化部署指南
- 4. 環境變數與組態
- 5. 資料庫設計與資料模型
- 6. API 設計與端點概覽
- 7. 工具與工具集（Tool/ToolSet）
- 8. Worker 流程與辯論循環（DebateCycle）
- 9. 第三方資料源與適配器（Adapters）
- 10. 測試策略（單元、整合、E2E）
- 11. 記錄、監控與可觀測性
- 12. 資安與合規建議
- 13. 發布、版本管理與資料遷移
- 14. 常見問題與故障排除
- 15. 擴充與路線圖建議
- 附錄 A. 專案結構樹
- 附錄 B. 常用指令與 API 操作範例

---

## 1. 專案簡介與目標
AgentScope Debate Platform 是一個基於 AgentScope 的自動化 AI 辯論平台。系統允許多個 AI 代理（Agents）針對特定主題進行辯論，並可使用搜尋與金融資料工具（SearXNG、DuckDuckGo、TEJ、Yahoo Finance）輔助論據生成。採微服務風格拆分 API 服務（FastAPI）與計算/任務服務（Celery Worker），以 Redis 為 Broker/Backend 與快取，並以 SQLite 儲存辯論存檔與組態。

核心價值：
- 透過主席（Chairman）進行賽前分析、回合總結與賽後整體分析。
- 正反雙方 Agents 依規則輪流辯論，支援工具呼叫（Web 搜尋、金融資料）。
- 以 API 暴露可供 Web/CLI/E2E 自動化整合。

商業目標：
- 作為內部研究輔助與 Demo 平台，快速驗證「多 Agent 協作＋工具使用」的策略。
- 擴展 Tool/ToolSet 與 Agent 管理，支援企業場景下的權限與審計。

---

## 2. 系統架構與元件說明

可視化圖表：
- 架構圖（Mermaid 原始檔）：diagrams/architecture.mmd
  - 匯出檔：SVG diagrams/exports/architecture.svg · PNG diagrams/exports/architecture.png
- 序列圖（Mermaid 原始檔）：diagrams/debate_sequence.mmd
  - 匯出檔：SVG diagrams/exports/debate_sequence.svg · PNG diagrams/exports/debate_sequence.png
- 概念 ERD（Mermaid 原始檔）：diagrams/erd.mmd
  - 匯出檔：SVG diagrams/exports/erd.svg · PNG diagrams/exports/erd.png

您可在支援 Mermaid 的檔案檢視器或文件系統中直接渲染，或將內容貼至 mermaid.live 觀看。並可在無 Mermaid 支援環境下使用已匯出的 SVG/PNG。

主要元件：
- API Service（FastAPI）
  - 位置：`api/`
  - 職責：RESTful API、DB 連線、工具註冊查詢、Agent 與 ToolSet 管理、辯論任務入口。
- Worker Service（Celery）
  - 位置：`worker/`
  - 職責：執行長時任務（辯論循環、工具調用）、主席分析與回合總結。
- Redis
  - 職責：Celery broker/backend、簡易快取（ToolRegistry 快取、Rate Limit 計數）、Pub/Sub（可擴展 SSE 推播）。
- SearXNG（外部服務容器）
  - 職責：隱私搜尋引擎供工具使用。
- Database（SQLite by default）
  - 職責：存檔辯論結果、Agent/ToolSet/關聯、Prompt 模板等。

關鍵互動流程（高層）：
1) 客戶端呼叫 API `POST /api/v1/debates` 建立辯論 → API 發出 Celery 任務（`run_debate_cycle`）。
2) Worker 啟動 `DebateCycle`：主席進行賽前分析、隊伍輪流辯論、會後存檔至 DB。
3) 工具呼叫由 Worker 透過 `ToolRegistry.invoke_tool` 執行，含參數驗證、快取、Rate Limit。
4) 客戶端輪詢 `GET /api/v1/debates/{task_id}` 或透過 SSE 取得進度；完成後可從 `/api/v1/debates` 查詢歷史。

---

## 3. 本地與容器化部署指南

前置需求：
- Docker 與 Docker Compose
- （選）本地 Python 3.10+ 以便直接執行測試或 API

快速啟動（Docker Compose）：
```bash
docker-compose up --build -d
# 驗證
docker-compose ps
# API 文件
open http://localhost:8000/docs
```

服務說明（來自 `docker-compose.yml`）：
- web: 選配 Web 前端（Gradio/Streamlit 之類）；連向 API
- api: FastAPI 服務（埠 8000）
- worker: Celery Worker（自動註冊工具並初始化 DB）
- redis: Redis 服務（埠 6379）
- searxng: SearXNG 服務（埠 8080）

本機直跑（開發用）：
- 需自備 Redis、SearXNG（或改用 DuckDuckGo 工具）
- 以 `uvicorn api.main:app --reload` 啟動 API
- 以 `celery -A worker.celery_app.app worker -l info` 啟動 Worker

---

## 4. 環境變數與組態

集中於 `.env` 與 Compose `environment`：
- LLM：`OLLAMA_HOST`, `OLLAMA_MODEL`
- Search：`SEARXNG_HOST/URL`, `GOOGLE_SEARCH_API_KEY`, `GOOGLE_CSE_ID`, `BING_SEARCH_API_KEY`, `BRAVE_SEARCH_API_KEY`
- 系統：`LOG_LEVEL`, `MAX_ROUNDS`, `DEFAULT_LANGUAGE`
- TEJ：`TEJ_API_KEY`（若使用台灣經濟新報資料）
- DB：`DATABASE_URL`（預設 `sqlite:///data/debate.db`）

注意：請勿將真實密鑰提交至版本庫或記錄於公開文檔；使用 dotenv 與部署平台的 Secret 管理。

---

## 5. 資料庫設計與資料模型

主要模型（`api/models.py`）：
- Agent：管理代理（名稱、角色、系統提示、專長、其他配置、時間戳）
- Tool：預留的工具表（現行工具註冊在記憶體中，DB 表可作為未來擴展）
- ToolSet：工具集（名稱、描述、工具名稱清單、是否全局、時間戳）
- AgentToolSet：Agent 與 ToolSet 多對多關聯
- PromptTemplate：提示詞範本（key, language, content, version）
- DebateArchive：辯論存檔（topic, analysis_json, rounds_json, logs_json, created_at）

初始化：`api/database.py:init_db()` 於 Worker 啟動時呼叫（也可在 API 啟動時）。

遷移策略建議：
- 短期：維持 SQLite + `create_all`。
- 中期：導入 Alembic 進行版本化遷移；上雲或切換 RDB（PostgreSQL）。

---

## 6. API 設計與端點概覽

文件：
- Swagger UI: `/docs`
- Redoc: `/redoc`
- OpenAPI: `/openapi.json`（亦見根目錄 `openapi.json`）

核心端點（節選）：
- Debate
  - `POST /api/v1/debates`：建立辯論（回傳 Celery task_id）
  - `GET /api/v1/debates`：列表辯論存檔
  - `GET /api/v1/debates/{task_id}`：查詢任務狀態（PENDING/SUCCESS/FAILURE）
  - `GET /api/v1/debates/{task_id}/stream`：SSE 串流（若已實作）
- ToolRegistry
  - `GET /tools`：列出已註冊工具（含 schema）
  - `POST /tools/test`：以 `name` + `kwargs` 測試工具
- Agent 管理（見 `api/agent_routes.py`）
  - `GET /api/v1/agents`：分頁、依角色篩選
  - `POST /api/v1/agents`：建立 agent
  - `GET /api/v1/agents/{id}` / `PUT` / `DELETE`
  - `GET /api/v1/agents/roles/available`：列出可用角色
- ToolSet 管理（見 `api/toolset_routes.py` + `api/toolset_schemas.py`）
  - 建立/更新/刪除 ToolSet，與 Agent 綁定關聯
  - 取得某 Agent 可用工具（assigned + global）

請參考 `tests/test_api.py` 與 `tests/test_e2e.py` 的呼叫範例。

---

## 7. 工具與工具集（Tool/ToolSet）

工具註冊（`api/tool_registry.py` + `worker/celery_app.py`）：
- 啟動 Worker 時註冊各工具：`SearXNGAdapter`, `DuckDuckGoAdapter`, `YFinanceAdapter`, 一系列 `TEJ*` 工具。
- `ToolRegistry.invoke_tool`：
  - 參數驗證（jsonschema）
  - 速率限制（Redis 計數）
  - 快取（Redis，TTL 由工具提供）
  - 執行 `tool.invoke(**params)`，回傳標準化結構

工具集服務（`api/toolset_service.py`）：
- 匯總 Agent 可用工具（assigned ToolSet + global ToolSet）
- 產生可嵌入 Prompt 的工具清單字串
- 自動維護全局工具集（若不存在則建立，並包含全部註冊工具）

新增工具步驟：
1) 在 `adapters/` 新增 `ToolAdapter` 子類（定義 `name/version/description/schema/invoke()`）。
2) 在 `worker/celery_app.py` 註冊該工具。
3) 若要加入全局工具集，重新啟動時會自動同步；或透過 ToolSet API 管理。

---

## 8. Worker 流程與辯論循環（DebateCycle）

主要程式：
- `worker/tasks.py: run_debate_cycle`：建立主席與隊伍、執行 `DebateCycle.start()`，最後將結果存 `DebateArchive`。
- `worker/debate_cycle.py`：管理辯論迴圈（回合輪替、證據匯集、結束匯總）。
- `worker/chairman.py`：主席角色，包含：
  - `pre_debate_analysis(topic)`：7 步分析管線（以 `worker/llm_utils.call_llm` 呼叫 LLM）
  - `summarize_round(...)`：每回合後從 Redis 擷取證據並總結
- `worker/llm_utils.py`：封裝 Ollama Chat API 呼叫；支援某些模型的 tool_calls → JSON 轉換（容錯）。
- `worker/tool_invoker.py`：包裝 `tool_registry.invoke_tool`。

可擴展點：
- SSE/進度推播：以 Redis Pub/Sub 推送中間事件至 API 轉發。
- 發言紀錄結構化：目前簡化為「證據作為發言的一部分」，可擴為完整 turn-by-turn transcript。

---

## 9. 第三方資料源與適配器（Adapters）

現有適配器：
- `SearXNGAdapter`：隱私搜尋；參數 `q/category/limit/engines`，回傳標準化結果陣列。
- `DuckDuckGoAdapter`：DuckDuckGo 搜尋；參數 `q/max_results`。
- `YFinanceAdapter`：Yahoo Finance；`symbol` 必填，`info_type` 為 `basic/history/news`。
- `TEJ*`：TEJ 多個端點支援（公司、股價、月營收、法人、融資券、IFRS 科目、基金/投信/海外基金、選擇權、期貨...）。

注意事項：
- API 金鑰與速率限制：請遵守服務條款，為 TEJ/Google/Bing/Brave 設置金鑰與上限保護。
- Normalize 與錯誤處理：各 adapter 已統一回傳格式，建議維持。

---

## 10. 測試策略（單元、整合、E2E）

現有測試：
- `tests/test_api.py`：API 基本測試（工具列表、工具測試）。
- `tests/test_e2e.py`：端到端流程（建立辯論 → 輪詢結果 → 驗證存檔）。

建議補強：
- 單元測試：ToolRegistry（參數驗證、快取/限流）、ToolSetService、Adapters Mock 測試。
- 整合測試：含 Redis/DB 的實際互動，驗證 Rate Limit 與 Cache 行為。
- 基準測試：長回合辯論（MAX_ROUNDS）探索資源瓶頸與延遲。

CI 建議：
- 在 GitHub Actions/自建 CI 執行 pytest，並產出 coverage 報告。

---

## 11. 記錄、監控與可觀測性

- 日誌：
  - API/Worker 皆應設定 `LOG_LEVEL`，輸出以 JSON 或結構化格式為佳。
  - 對第三方 API 呼叫建議記錄摘要（去敏），以便排錯。
- 監控：
  - Celery 任務耗時、失敗率；Redis 資源；SearXNG 延遲。
  - 如上雲可接入 Prometheus + Grafana；或以 ELK/EFK 收集日誌。
- 追蹤（可選）：
  - 以 request-id/correlation-id 串接 API → Worker → Tool 調用鏈。

---

## 12. 資安與合規建議

- 憑證管理：所有金鑰使用 Secret 管理，不進版控；禁止在例外訊息或日誌中洩漏。
- 出站請求風險控管：對外 HTTP 設置 allowlist（特別是工具可發起的搜尋/資料查詢）。
- 資料最小化：辯論存檔僅保留必要內容；如需匿名化，請設計脫敏流程。
- 服務端輸入驗證：API Schema 已有 Pydantic，工具層使用 jsonschema 校驗；請維持嚴格檢核。

---

## 13. 發布、版本管理與資料遷移

- 版本管理：建議 SemVer（API 契約、工具 schema 變更需 bump）。
- 發布流程：
  1) 建立 feature 分支與 PR。
  2) CI 測試通過、審查。
  3) 標註 tag 並部署（Compose 或 K8s）。
- 資料遷移：引入 Alembic；每次 schema 變更建立 migration；備份 `data/debate.db`。

---

## 14. 常見問題與故障排除

- API 無法啟動：
  - 檢查 `DATABASE_URL` 是否指向可寫目錄；檢視 `api/main.py` 日誌。
- Worker 無工具可用：
  - 確認 Worker 有執行註冊程式（`worker/celery_app.py`）且 Redis 連線正常。
- SearXNG 錯誤/逾時：
  - 檢查 `SEARXNG_HOST` 與容器狀態；改用 DuckDuckGo 作為回退。
- LLM 回傳空內容：
  - `worker/llm_utils.py` 已有警告與 tool_calls 容錯；確認模型/URL 設定與版本。
- TEJ 權限錯：
  - 檢查 `TEJ_API_KEY` 是否有效；觀察 rate limit。

---

## 15. 擴充與路線圖建議

短期（1–2 週）：
- 增加 API：ToolSet CRUD 與 Agent 連結端點全覆蓋（若尚未完整暴露）。
- SSE/WS：實作 `/debates/{id}/stream` 即時訊息推送。
- 補齊單元測試與 CI。

中期（1–2 月）：
- 引入 Alembic 遷移、PostgreSQL。
- 增加使用者/權限管理（RBAC），限制特定工具使用。
- 增加審計日誌（工具調用歷史、外部請求摘要）。
- 提供 Web 前端操作面板（Agent/ToolSet/辯論任務管理）。

長期：
- 觀測性完善（OpenTelemetry tracing）。
- 彈性佈署（K8s, HPA, Redis Cluster）。
- 工具市場與動態載入（Runtime 插件）。

---

## 附錄 A. 專案結構樹（摘要）
```
api/
  main.py              # FastAPI 入口、路由註冊
  agent_routes.py      # Agent 管理 API（CRUD/查詢）
  toolset_routes.py    # ToolSet 與 Agent-ToolSet API
  toolset_service.py   # ToolSet 業務服務
  tool_registry.py     # 工具註冊、快取、限流、調用
  models.py            # SQLAlchemy 模型
  database.py          # DB 引擎/Session 初始化
  schemas.py           # Pydantic Schemas

worker/
  celery_app.py        # Celery 啟動、工具註冊、DB 初始化
  tasks.py             # Celery 任務（run_debate_cycle, execute_tool）
  debate_cycle.py      # 辯論主循環
  chairman.py          # 主席 Agent：賽前分析/回合總結
  llm_utils.py         # LLM 呼叫封裝（Ollama）
  tool_invoker.py      # 工具呼叫封裝

adapters/
  searxng_adapter.py   # SearXNG 工具
  duckduckgo_adapter.py# DuckDuckGo 工具
  yfinance_adapter.py  # Yahoo Finance 工具
  tej_adapter.py       # TEJ 系列工具

tests/
  test_api.py          # API 測試
  test_e2e.py          # 端對端流程測試
```

---

## 附錄 B. 常用指令與 API 操作範例

啟動與檢查：
```bash
docker-compose up --build -d
docker-compose ps
```

查工具清單與測試：
```bash
curl http://localhost:8000/tools | jq
curl -X POST http://localhost:8000/api/v1/tools/test \
  -H 'Content-Type: application/json' \
  -d '{"name": "searxng.search", "kwargs": {"q": "agentic debate"}}'
```

建立辯論：
```bash
curl -X POST http://localhost:8000/api/v1/debates \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "Should AI be regulated?",
    "config": {
      "pro_team": [{"name": "AI-Pro-1"}, {"name": "AI-Pro-2"}],
      "con_team": [{"name": "AI-Con-1"}, {"name": "AI-Con-2"}],
      "rounds": 2
    }
  }'
```

查詢任務狀態：
```bash
curl http://localhost:8000/api/v1/debates/<task_id>
```

列出存檔：
```bash
curl http://localhost:8000/api/v1/debates
```

Agent 管理（示例）：
```bash
# 建立 Agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Chair-1",
    "role": "chairman",
    "system_prompt": "你是主席",
    "config_json": {"temperature": 0.2}
  }'

# 查詢（依角色）
curl 'http://localhost:8000/api/v1/agents?role=chairman'
```

---

若需將本文件同步至團隊知識庫（如 Confluence）或分割為「新手上路、運維手冊、二次開發指南」三份文件，可在本檔基礎上調整編排並加入組織特定流程（部署審批、變更管理、SLA、Runbook）。
