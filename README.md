# AgentScope Debate Platform

這是一個基於 AgentScope 的自動化 AI 辯論平台。系統允許多個 AI 代理（Agents）針對特定主題進行辯論，並支援即時搜尋工具（SearXNG）來增強論點。

## 系統架構

架構圖預覽：

![architecture](diagrams/exports/architecture.svg)

序列圖預覽：

![debate sequence](diagrams/exports/debate_sequence.svg)

ERD 預覽：

![ERD](diagrams/exports/erd.svg)

本專案採用微服務架構，主要包含以下組件：

- **API Service (FastAPI)**: 提供 RESTful API，處理辯論創建、查詢和管理。
- **Worker Service (Celery)**: 處理耗時的辯論邏輯和代理交互。
- **Redis**: 作為 Message Broker (Celery) 和 Result Backend，同時用於快取和 Pub/Sub 即時串流。
- **SearXNG**: 提供隱私保護的搜尋引擎功能，供 AI 代理查詢外部資訊。
- **Database (SQLite)**: 儲存辯論歷史記錄和歸檔。

## 快速開始

### 前置需求

- Docker
- Docker Compose

### 安裝與執行

1. **複製專案**
   ```bash
   git clone <repository-url>
   cd agentscope_debate
   ```

2. **啟動服務**
   使用 Docker Compose 構建並啟動所有服務：
   ```bash
   docker-compose up --build -d
   ```

3. **驗證服務**
   確認所有容器都已正常運行：
   ```bash
   docker-compose ps
   ```

## API 文件

當服務啟動後，您可以透過瀏覽器存取自動生成的 API 文件：

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) - 提供互動式的 API 測試介面。
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc) - 提供易讀的 API 參考文件。
- **OpenAPI JSON**: `openapi.json` 檔案已包含在專案根目錄中，或可透過 [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) 獲取。

### 主要端點

- `POST /api/v1/debates`: 創建新的辯論任務。
- `GET /api/v1/debates`: 獲取辯論列表。
- `GET /api/v1/debates/{task_id}`: 獲取特定辯論的狀態。
- `GET /api/v1/debates/{task_id}/stream`: 透過 SSE 實時串流辯論進度。
- `GET /tools`: 列出所有可用工具。

## 開發與測試

### 執行測試

專案包含端對端（E2E）測試，用於驗證系統的完整流程。

```bash
# 安裝測試依賴
pip install pytest requests

# 執行測試
python3 -m pytest tests/test_e2e.py
```

### 專案結構

```
agentscope_debate/
├── api/                 # FastAPI 應用程式
│   ├── main.py          # 應用程式入口
│   ├── database.py      # 資料庫連線與初始化
│   ├── models.py        # SQLAlchemy 模型
│   ├── schemas.py       # Pydantic 模型
│   └── tool_registry.py # 工具註冊中心
├── worker/              # Celery Worker
│   ├── celery_app.py    # Celery 應用程式設定
│   └── tasks.py         # 辯論任務邏輯
├── core/                # 核心邏輯與工具
├── adapters/            # 第三方服務適配器 (如 SearXNG)
├── tests/               # 測試文件
├── docker-compose.yml   # Docker Compose 設定
└── openapi.json         # OpenAPI 規範文件
```

## 維護

- 交付企劃與維護指南：請參考 PROJECT_DELIVERY_PLAN_zh-TW.md（包含架構、部署、資料庫、API、工具集、Worker 流程、測試、安全與路線圖）。

- **資料庫遷移**: 目前使用 `init_db()` 自動建立表格。
- **新增工具**: 在 `adapters/` 中實作工具，並在 `worker/celery_app.py` 和 `api/main.py` 中註冊。
