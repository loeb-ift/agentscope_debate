# AI 辯論平台軟體設計文件（SDD）

文件狀態: Draft v1.0  
作者: ——  
審核: ——  
日期: 2025-12-04

---

1. 文件總則（Document Control）
- 目的: 本文件以規格驅動開發（Specification-Driven Development, SDD）為核心，提供完整、可驗證、可追溯的設計規格。任何程式碼實作均被視為對本規格的可執行驗證。
- 範圍: 定義 AI 辯論平台的業務需求、系統架構、資料模型、API 介面、工作流、安全性、部署、測試與驗收標準。
- 讀者: 產品經理、系統架構師、後端/前端/資料/QA 工程師、運維人員。
- 變更管控: 任何變更需建立 Change Request（CR），更新「需求可追溯矩陣」並同步驗收測試案例。

2. 名詞與縮寫（Glossary）
- SDD: Specification-Driven Development
- LLM: Large Language Model
- CoT: Chain of Thought
- Evidence Board: 共享證據板（Redis 列表）
- Chairman: 主席智能體
- Team_Pro/Team_Con: 正反方團隊

3. 系統目標與非目標（Goals & Non-Goals）
3.1 目標
- G1 過程啟發性：呈現 AI 完整思考路徑與攻防邏輯，強化決策啟發。
- G2 透明可追溯：完整記錄推理步驟、工具調用與共識/分歧演變並可復盤。
- G3 模組化擴展：以工具與智能體為邏輯邊界，支持平行擴展。
- G4 在地化體驗：預設繁體中文 UI 與內容生成。

3.2 非目標
- NG1 不以「勝負判定」為唯一產出；重視過程而非僅結論。
- NG2 非即時語音辯論；本期聚焦文字與工具輔助。

4. 系統約束（Technical Constraints）
- C1 架構: Docker Compose 微服務（web, api, worker, redis, db, searxng）。
- C2 LLM 統一介面: 僅透過 OLLAMA_HOST/OLLAMA_MODEL 設定（Ollama/OpenAI Compatible）。
- C3 非同步: 耗時操作一律以 Celery 任務執行，禁止阻塞 HTTP。
- C4 禁止硬編碼: Prompt/規則配置存於 DB 或設定檔。
- C5 語言: 全系統繁體中文。

5. 系統上下文與架構（Context & Architecture）
5.1 上下文
- 外部系統: 搜尋（SearXNG/Google/Bing）、財經資料（yfinance/TEJ/stockdex）、LLM（Ollama）。
- 使用者: 視覺化觀察者、建立辯題者、Agent 管理者。

5.2 服務編排（docker-compose）
| 服務 | 埠口 | 依賴 | 職責 |
|---|---|---|---|
| web (Gradio) | 7860:7860 | api | 前端 UI，輪詢狀態，渲染思考流 |
| api (FastAPI) | 8000:8000 | redis, db | REST API、資料模型、任務分發 |
| worker (Celery) | - | redis, db, searxng | 執行智能體推理與工具調用 |
| redis | 6379:6379 | - | Broker、快取、共享證據板 |
| db (SQLite/pg 可替換) | - | - | 持久化（Agent/Prompt/Archive） |
| searxng | 8080:8080 | - | 私有搜尋引擎 |

5.3 環境變數規格（.env）
```ini
# LLM
OLLAMA_HOST=http://10.227.135.98:11434
OLLAMA_MODEL=gpt-oss:20b

# Search
GOOGLE_SEARCH_API_KEY=
GOOGLE_CSE_ID=
BING_SEARCH_API_KEY=

# System
LOG_LEVEL=INFO
MAX_ROUNDS=3
DEFAULT_LANGUAGE=zh-TW
```

6. 記憶分層與資料設計（Memory & Data Design）
6.1 記憶分層
- L1 持久化（SQLite/PG）
  - Agent(id, name, system_prompt, config_json, created_at)
  - Tool(id, name, type, json_schema, enabled)
  - PromptTemplate(id, key, language, content, version)
  - DebateArchive(id, topic, analysis_json, rounds_json, logs_json, created_at)
- L2 高速共享（Redis）
  - Evidence Board: key `debate:{id}:evidence` → list[JSON{source, ts, content, score}]
  - Session Context: key `debate:{id}:context` → list[Message]
- L3 上下文記憶（AgentScope）
  - Token 超限觸發摘要：`summary + last_n_messages`
- L4 長期知識（Vector Store）
  - 歷史辯論 embeddings 與語意檢索

6.2 事件與日誌
- 事件模型 Event(id, debate_id, type, payload, ts)
- 日誌分類：audit, agent_thought, tool_io, api_access

7. 功能需求（Functional Requirements）
FR-001 智能體管理
- 輸入: 前端表單（name, prompt, config）
- 流程: 驗證 → DB 寫入 → 自動注入「引用獎勵指令」
- 輸出: agent_id
- 約束: 系統注入文案（不可移除）：
  - 你的目標是贏得辯論。每一個由工具資料支援的論點權重為純邏輯的 2 倍；未引用資料視為主觀臆斷。

FR-002 工具註冊與規格
- 啟動自動註冊核心工具：SearXNG, yfinance, stockdex, TEJ API
- 每個工具必附 JSON Schema 與示例，供 LLM function calling

7.1 工具整合設計（第三方 API 作為工具）
7.1.1 生命週期（Lifecycle）
- 註冊（Register）: 以 Tool Registry 建立工具定義（名稱、版本、JSON Schema、授權方式、端點、限流策略、快取策略、錯誤映射）。
- 驗證（Validate）: 後端對端點做健康檢查與契約測試（schema/型別/示例）。
- 啟用（Activate）: 允許在辯論任務中被 LLM 呼叫；狀態=enabled。
- 調用（Invoke）: Worker 透過 Adapter 呼叫第三方 API，遵循限流/重試/快取/觀測性規範。
- 觀測（Observe）: 匯報 metrics（成功率、延遲、429/5xx）、記錄 tool_io 日誌、串接 traceId。
- 版本化/汰換（Version/Deprecate）: 支援破壞性更新以新版本名稱發佈；舊版進入 deprecating 狀態並設定 EOL。

7.1.2 Tool Adapter 介面（抽象）
- 屬性: name, version, description, auth_config, rate_limit_config, cache_ttl, schema
- 方法:
  - describe() -> JSON Schema（含 examples、enum、default）
  - validate(params: dict) -> None/raise ERR-VALIDATION
  - auth(req) -> req（注入 API Key/OAuth/HMAC）
  - invoke(params) -> ToolResult（data, raw, used_cache, cost, citations）
  - should_cache(params) -> bool / cache_key(params)
  - map_error(http_status, body) -> CanonicalError

7.1.3 JSON Schema 規範（最低要求）
- type=object, properties, required, additionalProperties=false
- 嚴格型別與範圍（minimum/maximum/pattern/enum），提供 examples
- 錯誤碼說明與典型回應示例（200/400/401/403/404/429/5xx）

7.1.4 授權模式（Authentication）
- API Key: Header（如 X-API-Key/Authorization: Bearer <token>）
- OAuth2 Client Credentials: 取得 access_token 後快取於 Redis（TTL<=token_expiry-60s）
- HMAC 簽名: 依供應商演算法產生 signature 與 timestamp
- 網域白名單/自簽憑證: 只允許預先登記之 baseURL

7.1.5 限流與穩定性（Rate Limit & Resilience）
- 本地令牌桶（token bucket）+ 分散式快取協調（Redis）
- 自動退避重試: 對 429/5xx 指數退避（base=250ms, factor=2, jitter=±20%），最大嘗試 3 次
- 熔斷器（circuit breaker）: 連續錯誤超閾值開啟，冷卻期後半開試探

7.1.6 快取策略（Caching）
- 適用: 具可重複性/查詢型 GET 類工具；不可用於具副作用的 POST
- 鍵: tool:{name}:{hash(params)}；TTL 依資料新鮮度（如新聞 2m、股價 15s、靜態百科 24h）
- 調用流程: 命中快取直接返回並標示 used_cache=true；未命中則落盤並回填快取

7.1.7 錯誤映射（Error Mapping）
- 供應商錯誤 → 平台錯誤碼：
  - 400/422 → ERR-VALIDATION
  - 401/403 → ERR-AUTH
  - 404 → ERR-NOT-FOUND
  - 429 → ERR-RATE-LIMIT（附 retry_after 秒）
  - 5xx/網路 → ERR-UPSTREAM

7.1.8 可觀測性（Observability）
- 日誌：tool_io（name, params_hash, status, duration_ms, http_status, used_cache, error_code, trace_id）
- 指標：成功率、P50/P95 延遲、429/5xx 比例、快取命中率
- 追蹤：將 trace_id 從 API → worker → adapter → 供應商呼叫串接

7.1.9 安全（Security）
- 祕密管理：僅從環境變數/祕密管理器讀取，禁止硬編碼
- 網路: 僅允許 allowlist 的 baseURL；TLS 強制
- 敏感資料: 日誌打碼（API key、token、簽名）

7.1.10 測試（Testing）
- 契約測試：以 JSON Schema 驗證入參/出參
- 錄製與重播：VCR/錄製夾具以降低外部不穩定性
- 沙盒：若供應商提供 sandbox，預設用於 CI

7.1.11 具體範例（Adapters）
A) TEJ REST API（台灣市場）
- baseURL: https://api.tej.com.tw/v1
- Auth: Authorization: Bearer <TEJ_API_KEY>
- 典型方法：/financials?symbol=2330.TW&period=annual&limit=5
- JSON Schema（摘要）:
```json
{
  "name": "tej.financials",
  "description": "查詢台灣上市公司財務資料",
  "parameters": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "symbol": {"type": "string", "pattern": "^[0-9]{4}\\.TW$"},
      "period": {"type": "string", "enum": ["annual", "quarterly"], "default": "annual"},
      "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}
    },
    "required": ["symbol"]
  }
}
```
- 轉換：將供應商欄位（如 eps, roe, roa, debt_ratio）正規化為平台欄位
- 快取：TTL=6h；錯誤對應 429→ERR-RATE-LIMIT
- 健檢：GET /status 與權限測試（最小查詢）

B) SearXNG（私有搜尋）
- baseURL: http://searxng:8080
- 方法：/search?q=...&categories=news&language=zh-TW
- JSON Schema（摘要）:
```json
{
  "name": "searxng.search",
  "description": "以關鍵字進行隱私搜尋",
  "parameters": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "q": {"type": "string", "minLength": 2},
      "category": {"type": "string", "enum": ["general", "news", "science"], "default": "general"},
      "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10}
    },
    "required": ["q"]
  }
}
```
- 正規化：title/url/snippet/source/relevance，產生 citations 用於發言引用
- 快取：TTL=2m；敏感詞/成人內容過濾可於 adapter 層實作

C) yfinance（Python library）
- 介面：以內部 wrapper 封裝為工具；輸入 {symbol, period, interval}
- 輸出：正規化 OHLCV、最新價、時間戳；快取 TTL=15s

7.1.12 Worker 調用偽碼（含重試/快取/觀測性）
```python
@instrumented
@retry(on=[429, 500, 502, 503], backoff=exp2_jitter, max_tries=3)
def call_tool(tool_name, params):
    adapter = registry.get(tool_name)
    schema = adapter.describe()
    validate_against_schema(params, schema)

    key = f"tool:{tool_name}:{hash_params(params)}"
    if adapter.should_cache(params):
        cached = redis.get(key)
        if cached:
            return {**cached, "used_cache": True}

    req = adapter.auth({"params": params})
    t0 = now()
    try:
        result = adapter.invoke(req["params"])  # 包含 data/raw/citations
        duration = ms_since(t0)
        metrics.observe(tool=tool_name, ok=True, ms=duration)
        if adapter.should_cache(params):
            redis.setex(key, adapter.cache_ttl, result)
        return {**result, "used_cache": False}
    except UpstreamError as e:
        duration = ms_since(t0)
        metrics.observe(tool=tool_name, ok=False, ms=duration, code=e.code)
        raise map_to_platform_error(e)
```

FR-003 主席賽前分析（7 步）
- 觸發: Topic 提交
- 產出: AnalysisReport（類型、要素、因果鏈、子題、戰略、Prompt、工具建議）
- 落地: Redis + DB

FR-004 辯論循環
- 參數: 正/反方隊伍、輪次 N
- 每輪: 主席引導 → 正方發言（可動態工具）→ 反方反駁（須讀取 evidence）→ 主席共識總結
- 結束: 主席結辯報告 Final_Report

FR-005 前端視覺化
- 即時顯示思考流（Thinking/Tool IO）與引用標註
- 歷史復盤：時間軸還原、查看 Prompt/ToolData/CoT

FR-006 角色與設定管理
- 團隊成員 CRUD、輪次設定、語言設定（預設 zh-TW）

8. 非功能需求（Non-Functional Requirements）
- NFR-001 可用性: 服務 99% 可用，重試策略與健康檢查
- NFR-002 性能: 單輪工具+推理 P95 < 5s（視模型與工具而定，可配置超時）
- NFR-003 擴展性: 工具/Agent 水平擴展；worker 可水平擴容
- NFR-004 安全: API 金鑰/祕密以環境變數或密鑰管理器；審計日誌保留 90 天
- NFR-005 i18n: 基礎多語支持但預設繁中

9. API 介面規格（OpenAPI 摘要）
9.1 路由概覽
- POST /api/v1/debates: 建立辯論（topic, teams, rounds）
- GET /api/v1/debates/{id}: 查詢辯論狀態與結果
- GET /api/v1/debates/{id}/stream: SSE/輪詢取得思考流
- POST /api/v1/agents: 建立/更新智能體
- GET /api/v1/agents: 列出智能體
- POST /api/v1/tools/test: 測試工具規格/連線
- GET /api/v1/replays: 歷史辯論列表

9.2 範例規格（YAML 節選）
```yaml
openapi: 3.0.3
info:
  title: AI Debate Platform API
  version: 1.0.0
paths:
  /api/v1/debates:
    post:
      summary: Create a debate
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [topic, pro_team, con_team, rounds]
              properties:
                topic: { type: string }
                pro_team: { type: array, items: { type: string } }
                con_team: { type: array, items: { type: string } }
                rounds: { type: integer, minimum: 1, maximum: 10 }
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: { type: string }
                  status: { type: string, enum: [created, running, completed, failed] }
```

10. 工作流詳解（Workflows）
10.1 主席賽前分析（落實 7 步管線）
- 類型識別 → 核心要素 → 因果鏈 → 子問題 → 戰略 → 主席手卡 Prompt → 工具策略
- 任務實作: Celery 任務 chain，結果寫入 Redis/DB

10.2 辯論循環（Pseudo Code）
```python
for round in range(1, N+1):
    Chairman.speak(context="本輪核心議題...")
    pro = select_agent(Team_Pro)
    obs = pro.think_and_act()            # 可能多次 tool
    Redis.lpush(evidence_key, obs)
    pro.speak(content, citations)

    con = select_agent(Team_Con)
    con.read_evidence(Redis.lrange(evidence_key, 0, -1))
    con.speak(content, counter_citations)

    Chairman.summarize(consensus, divergence)
Final_Report = Chairman.generate_report()
```
- 前端需即時顯示思考狀態：例如「正在查詢 TEJ…」

11. 前端規格（Frontend）
- 框架: Gradio Blocks；語言: zh-TW
- 頁面：
  1) 辯論大廳：輸入、團隊設定、輪次、聊天區、思考流、主席分析進度
  2) 歷史復盤中心：列表、時間軸、Prompt/Tool/CoT 詳情
  3) 智能體工坊：Agent CRUD
  4) 工具庫：工具配置
  5) 提示詞控制台：PromptTemplate 編輯

11.1 前端工具管理（Tool Registry UI）
- 目的：提供非工程使用者以圖形化方式新增/測試/啟用工具。
- 元件：
  - 工具清單（名稱、版本、狀態、限流/快取策略摘要、最近延遲/成功率）
  - 工具詳情面板（JSON Schema 檢視器、示例請求/回應、錯誤碼對照表）
  - 健康檢查與測試（以最小示例調用，顯示原始回應與正規化結果）
  - 啟用/停用/版本切換操作按鈕
- 表單驗證：
  - JSON Schema 以即時校驗方式呈現（型別、enum、pattern）
  - baseURL 必須符合 allowlist；認證欄位遮罩顯示
- 事件與狀態：
  - 建立/更新/測試動作以非同步方式發送至 API，UI 顯示待處理/成功/失敗狀態
  - 即時讀取 metrics 與最近錯誤以提示風險

11.2 前端辯論視覺化（強化）
- 思考流區域：
  - 顯示 agent 的 "Thinking" 與工具調用卡片（名稱、參數摘要、延遲、是否命中快取、引用連結）
  - 支援折疊/展開原始工具回應與引用來源（citations）
- 證據板視圖：
  - 以清單或面板顯示 Redis evidence 條目（來源、可信度、時間戳）
  - 支援以來源/關鍵字過濾
- Replay 時間軸：
  - 每個節點可打開當時的 Prompt、Tool Data、CoT 紀錄

11.3 前端檔案連結（工程落地範例）
- 參考 Adapter 與測試樣板位置：
  - /Users/loeb/Desktop/agentscope_debate/adapters/*.py
  - /Users/loeb/Desktop/agentscope_debate/tests/*.py

12. 安全與合規（Security）
- API Key 管理與最小權限
- 速率限制與防止資源濫用（基於 IP/token）
- 日誌隱私: 避免記錄敏感輸入；支援 PII 打碼
- 供應鏈安全: 鎖定相依版本，容器鏡像掃描

13. 部署與運維（Deployment & Ops）
- Docker Compose 一鍵啟動；健康檢查（/healthz）與依賴啟動順序
- 可選資料庫：預設 SQLite，生產建議 PostgreSQL
- 佈署參數化：透過 .env 控制

14. 監控與可觀測性（Observability）
- 指標: 任務耗時、工具成功率、P95 Latency、輪次完成率
- 日誌: 分層（api_access, tool_io, agent_thought, audit）
- 追蹤: 任務 ID 與請求 ID 串接

15. 測試策略（Test Strategy）
- 單元測試：資料模型、工具封裝、輔助函數
- 整合測試：API 端點、Celery 任務鏈、Redis 交互
- 端到端：建立辯題→完成 7 步→多輪辯論→產生 Final_Report→復盤可見
- 測試資料與 Mock：工具外呼以假資料/錄製（VCR）

16. 驗收標準（Acceptance Criteria）
- AC-001 環境一鍵啟動：`docker-compose up` 無錯誤
- AC-002 完成 7 步分析並推薦 TEJ/yfinance（以「台積電未來五年股價趨勢」為例）
- AC-003 辯論過程可見引用（如「根據 TEJ 2023 Q4 報表…」）
- AC-004 復盤中心可查看完整思考路徑與原始數據
- AC-005 在地化：所有 UI/預設文本為繁體中文

17. 風險與緩解（Risks & Mitigations）
- R1 工具不穩定/速率限制 → 加入退避重試、快取與配額保護
- R2 LLM 回應漂移 → 提示詞版本化與 A/B 測試、關鍵規則系統注入
- R3 Token 超限 → 自動摘要策略（summary + last_n）
- R4 效能瓶頸 → worker 水平擴容與任務切片

18. 需求可追溯矩陣（Traceability）
| 需求 | 設計/模組 | API/資料 | 測試 | 驗收 |
|---|---|---|---|---|
| FR-001 | Agent 模組 | POST /agents, Agent 表 | 單元/整合 | AC-001 |
| FR-002 | Tool 模組 | POST /tools/test, Tool 表 | 單元/整合 | AC-001 |
| FR-003 | 分析管線 | Celery chain, Redis | E2E | AC-002 |
| FR-004 | 辯論引擎 | /debates, Redis evidence | E2E | AC-003 |
| FR-005 | 前端 UI | web/stream | E2E/視覺 | AC-004-005 |

19. 附錄（Appendix）
19.1 工具 JSON Schema 範例（SearXNG）
```json
{
  "name": "searxng.search",
  "description": "以關鍵字進行隱私搜尋",
  "parameters": {
    "type": "object",
    "properties": {
      "q": {"type": "string"},
      "category": {"type": "string", "enum": ["general", "news", "science"]},
      "limit": {"type": "integer", "minimum": 1, "maximum": 20}
    },
    "required": ["q"]
  }
}
```

19.2 Redis Key 規格
- debate:{id}:evidence → list of JSON
- debate:{id}:context  → list of Message

19.3 錯誤碼約定（示例）
- ERR-VALIDATION: 400 請求驗證錯誤
- ERR-TOOL-TIMEOUT: 504 工具超時
- ERR-LLM-FAIL: 502 LLM 響應失敗

本文件為 SDD 的權威來源。所有開發、測試與驗收活動均應以本文件為依據與依循。