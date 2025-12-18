# AgentScope 自動化 AI 辯論平台

這是一個基於 AgentScope 框架開發的自動化 AI 辯論平台，支援多個 AI 代理針對特定主題進行結構化辯論，並整合多種外部工具來增強論點質量。

## 🎯 平台特色

- **多代理辯論**: 支援正方、反方、中立方多團隊辯論模式
- **即時資訊檢索**: 整合 SearXNG、DuckDuckGo、YFinance 等搜尋工具
- **金融資料支援**: 整合 TEJ 台灣經濟新報資料庫，提供專業金融數據
- **即時串流**: 透過 Server-Sent Events (SSE) 提供即時辯論進度
- **評分機制**: 自動評分系統，追蹤各方論點質量
- **合規審核**: 內建 Guardrail Agent 與 Base Contract，防止幻覺與錯誤推論
- **Web 介面**: 直觀的 Gradio 前端介面，便於操作與監控

## 🏗️ 系統架構

### 架構圖
![系統架構圖](diagrams/exports/architecture.svg)

### 辯論流程圖
![辯論序列圖](diagrams/exports/debate_sequence.svg)

### 資料庫 ERD
![資料庫 ERD](diagrams/exports/erd.svg)

## 📦 核心組件

### 後端服務
- **API Service (FastAPI)**: RESTful API 服務，處理辯論創建、查詢和管理
- **Worker Service (Celery)**: 非同步任務處理，執行辯論邏輯和代理交互
- **Guardrail Service**: 專職的合規審查服務，攔截違規輸出
- **Redis**: 訊息代理、結果後端、快取和 Pub/Sub 即時串流
- **SearXNG**: 隱私保護的搜尋引擎，提供外部資訊查詢
- **SQLite 資料庫**: 儲存辯論歷史記錄和歸檔資料

### 前端介面
- **Gradio Web App**: 直觀的 Web 介面，支援辯論配置和即時監控
- **即時狀態更新**: 自動輪詢和 SSE 串流顯示辯論進度

### 工具整合 (Toolset Ecosystem)
- **數據運算 (ODS/OSU)**: 底層量化運算服務，處理 CSV 並產出統計圖表
- **事實查核 (Verifiers)**: 提供 `financial.get_verified_price` 進行多源數據驗證
- **金融套件**: 整合 TEJ 專業數據、TWSE 官方數據與 Yahoo Finance
- **搜尋路由**: 智能分流 Google CSE (高品質) 與 SearXNG (免費) 搜尋
- **實體關係**: 查詢集團母子公司關係與產業鏈上下游

## 🚀 快速開始

本專案已完全容器化，最推薦的啟動方式是使用 Docker Compose。此方法會一次性啟動所有必要的服務，包括 API 後端、Celery Worker、前端介面、Redis 和 SearXNG 搜尋引擎。

### 前置需求
- Docker 20.10+
- Docker Compose 2.0+

### 啟動步驟

1. **複製專案**
   ```bash
   git clone <repository-url>
   cd agentscope_debate
   ```

2. **配置環境變數**
   專案可能需要特定的 API 金鑰或配置。請複製 `.env.example` 檔案來建立您的本地設定：
   ```bash
   cp .env.example .env
   ```
   接著，編輯 `.env` 檔案並填入必要的數值，例如 `TEJ_API_KEY` 或 `OPENAI_API_KEY`。

3. **一鍵啟動所有服務**
   執行以下指令來構建映像檔並在背景啟動所有容器：
   ```bash
   docker-compose up --build -d
   ```
   - `--build`: 強制重新構建映像檔，確保程式碼更新生效。
   - `-d`: 在背景模式 (detached mode) 執行。

4. **驗證服務狀態**
   等待約 1-2 分鐘讓所有服務完成初始化後，執行以下指令檢查所有容器是否正常運行：
   ```bash
   docker-compose ps
   ```
   您應該會看到 `api`, `worker`, `web`, `redis`, `searxng` 等服務的狀態為 `running` 或 `up`。


### 服務端口
- **API 服務**: http://localhost:8000
- **Web 前端**: http://localhost:7860
- **SearXNG**: http://localhost:8888

## 📖 API 文件

服務啟動後可透過以下方式存取 API 文件：

- **Swagger UI**: http://localhost:8000/docs - 互動式 API 測試介面
- **ReDoc**: http://localhost:8000/redoc - 易讀的 API 參考文件
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 主要 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/debates` | POST | 創建新的辯論任務 |
| `/api/v1/debates` | GET | 獲取辯論列表 |
| `/api/v1/debates/{task_id}` | GET | 獲取特定辯論狀態 |
| `/api/v1/debates/{task_id}/stream` | GET | SSE 即時串流辯論進度 |
| `/api/v1/agents` | GET | 獲取代理列表 |
| `/api/v1/tools` | GET | 列出所有可用工具 |
| `/api/v1/toolsets` | GET | 獲取工具集配置 |

## 🛠️ 開發指南

### 專案結構
```
agentscope_debate/
├── api/                 # FastAPI 應用程式
│   ├── main.py          # 應用程式入口點
│   ├── database.py      # 資料庫連線與初始化
│   ├── models.py        # SQLAlchemy 資料模型
│   ├── schemas.py       # Pydantic 資料驗證模型
│   ├── tool_registry.py # 工具註冊中心
│   └── routes/          # API 路由模組
├── worker/              # Celery Worker
│   ├── celery_app.py    # Celery 應用程式設定
│   └── tasks.py         # 辯論任務邏輯
├── adapters/            # 第三方服務適配器
│   ├── searxng_adapter.py      # SearXNG 搜尋適配器
│   ├── duckduckgo_adapter.py   # DuckDuckGo 適配器
│   ├── yfinance_adapter.py     # YFinance 股票資料適配器
│   ├── tej_adapter.py          # TEJ 金融資料適配器
│   └── python_tool_adapter.py  # Python 工具適配器
├── web/                 # 前端介面
│   ├── app.py          # Gradio 前端應用
│   └── requirements.txt # 前端依賴
├── core/               # 核心邏輯與工具
├── tests/              # 測試文件
├── diagrams/           # 架構圖文件
└── docker-compose.yml  # Docker 編排配置
```

### 執行測試

```bash
# 安裝測試依賴
pip install pytest requests

# 執行端對端測試
python3 -m pytest tests/test_e2e.py

# 執行單元測試
python3 -m pytest tests/unit/
```

### 新增工具適配器

1. 在 `adapters/` 目錄創建新的適配器類別
2. 實作 `ToolAdapter` 介面
3. 在 `api/main.py` 和 `worker/celery_app.py` 中註冊適配器
4. 更新 API 文件說明

## 📊 功能特性

### 辯論管理
- **多輪次辯論**: 支援可配置的辯論輪次
- **交叉質詢**: 啟用/禁用交叉質詢功能
- **團隊配置**: 靈活的團隊和代理分配
- **即時評分**: 自動評分和論點質量追蹤

### 代理系統
- **角色定義**: 主席、辯手、專家等不同角色
- **專業領域**: 針對不同主題配置專業代理
- **系統提示**: 可自定義的系統提示詞
- **配置管理**: 靈活的代理配置管理
- **行為約束**: 透過 Base Contract 強制約束 Agent 行為邊界
- **主席戰略引導**: 主席分析結果將直接注入其他 Agent，用於：
  - **戰場劃定**: 限制辯論邊界與關鍵指標
  - **情報同步**: 共享背景調查結果，避免資訊落差
  - **時間錨定**: 統一資料庫有效時間，防止幻覺
  - **論證標準**: 設定高分審查框架（如必須包含 CAPM）

### 工具與數據生態 (Toolset & OSU)

本平台採用 **數據與邏輯分離** 的架構，透過 **Operational Storage Unit (OSU)** 確保數據的公信力與處理效能。

#### 1. 詳細工具清單
| 模組 | 關鍵工具名稱 | 核心功能 |
| :--- | :--- | :--- |
| **自動化分析** | `chairman.eda_analysis` | 辯論開始時自動拉取數據並生成 EDA 報表 |
| **數據運算** | `ods.eda_describe` | 底層 OSU 數據處理，產生統計圖與缺失值分析 |
| **事實查核** | `financial.get_verified_price` | 交叉比對 TEJ/TWSE/Yahoo 產出公信力股價 |
| **金融分析** | `tej.financial_summary` | 獲取標準化財報、法人持股與會計科目 |
| **智能檢索** | `search.router` | 根據角色自動路由至 Google CSE 或 SearXNG |
| **集團實體** | `internal.get_industry_tree` | 查詢公司所屬產業鏈與集團關聯實體 |

#### 2. OSU 數據流轉邏輯
為了在有限的 Token 限制下處理大量金融數據，系統實作了 **「數據在 OSU 流轉，Agent 在 Context 引用」** 的機制：

1.  **數據攝取 (Ingestion)**: 適配器將抓取的原始數據 (CSV) 存入 OSU 磁碟空間。
2.  **證據註冊**: 系統透過 `EvidenceLifecycle` 為該數據註冊唯一 Evidence ID。
3.  **ODS 分析**: `ods.eda_describe` 讀取 OSU 檔案，產出視覺化圖表與摘要，並更新 Metadata。
4.  **Agent 引用**: Agent 的上下文僅持有證據 ID 與摘要路徑，發言時透過 ID 進行精準引用（如 `[Ref: ev_eda_001]`）。

#### 3. 證據生命週期管理 (Evidence Lifecycle)
系統透過 `worker/evidence_lifecycle.py` 實作了嚴格的證據狀態機，確保數據流轉的透明性：

- **Ingest (寫入)**: 原始數據進入 OSU，建立 `DRAFT` 證據，並透過 `inputs_hash` (MD5) 自動去重。
- **Verify (驗證)**: 執行 **數據誠信檢查 (Data Honesty)**。若數據為空或錯誤則隔離 (`QUARANTINE`)，通過則標記為 `VERIFIED` 並分配 **TTL (生存時間)**。
- **Aging (老化)**: 定期將過期證據轉為 `STALE`，強制 Agent 重新獲取最新市場數據。
- **Citation (引用)**: 透過 `create_checkpoint` 鎖定當前辯論的所有 `VERIFIED` ID，實現「事實錨定」。

![工具架構圖](diagrams/exports/tool_architecture.svg)

## 🔧 維護與部署

### 資料庫管理
- 使用 `init_db()` 自動建立資料表
- SQLite 資料庫檔案位於 `instance/` 目錄
- 支援資料庫遷移和版本控制

### 服務監控
```bash
# 查看服務日誌
docker-compose logs api
docker-compose logs worker

# 監控 Celery 任務
celery -A worker.celery_app flower

# 健康檢查
curl http://localhost:8000/health
```

### 效能優化
- Redis 快取機制減少重複查詢
- 非同步任務處理避免阻塞
- 連線池管理資料庫和 Redis 連線
- 記憶體使用監控和優化

## 📝 相關文件

- **專案交付計劃**: [PROJECT_DELIVERY_PLAN_zh-TW.md](PROJECT_DELIVERY_PLAN_zh-TW.md)
- **AI 辯論平台開發指南**: [AI_Debate_Platform_Dev_Guide.md](AI_Debate_Platform_Dev_Guide.md)
- **前端使用指南**: [FRONTEND_USER_GUIDE.md](FRONTEND_USER_GUIDE.md)
- **工具集架構**: [TOOLSET_ARCHITECTURE.md](TOOLSET_ARCHITECTURE.md)
- **TEJ 驗證報告**: [TEJ_VERIFICATION_REPORT.md](TEJ_VERIFICATION_REPORT.md)

## 🐛 問題回報

如果您遇到任何問題或有功能建議，請透過以下方式回報：

1. 檢查現有問題列表
2. 提供詳細的重現步驟
3. 包含相關的日誌資訊
4. 說明預期行為和實際行為

## 🤝 貢獻指南

我們歡迎任何形式的貢獻！請參閱：
- [CONTRIBUTING.md](agentscope/CONTRIBUTING.md)
- [CONTRIBUTING_zh.md](agentscope/CONTRIBUTING_zh.md)

## 📄 授權協議

本專案採用 MIT 授權協議 - 詳見 [LICENSE](agentscope/LICENSE) 文件。

## 🙏 致謝

- **AgentScope 團隊**: 提供優秀的多代理框架
- **SearXNG 專案**: 隱私保護的搜尋引擎
- **TEJ 台灣經濟新報**: 專業金融資料支援
- **開源社群**: 所有貢獻者和使用者

---

**版本**: 1.0.0  
**最後更新**: 2024年12月  
**維護者**: AgentScope Debate Platform Team