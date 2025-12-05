# AI Debate Platform 開發待辦事項 (TODO List)

本文件旨在追蹤開發進度，確保在不同開發階段與 LLM session 切換時能保持上下文連貫。

## 1. 專案初始化 (Project Initialization)
- [x] 建立專案目錄結構 (`api`, `web`, `worker`, `adapters`, `tests`)
- [x] 建立 `docker-compose.yml` 定義服務編排
- [x] 建立 `.env` 環境變數設定檔
- [x] 建立共享資料目錄 (`data`) 並設定 `.gitignore`

## 2. 基礎服務骨架 (Service Skeletons)
### 2.1 API Service (FastAPI)
- [x] 建立 `api/Dockerfile`
- [x] 建立 `api/requirements.txt` (FastAPI, Uvicorn, SQLAlchemy, Redis, Celery, etc.)
- [x] 建立 `api/main.py` (Hello World endpoint)
- [x] 定義資料庫模型 (`models.py`) - 參照 SDD 6.1
    - [x] Agent
    - [x] Tool
    - [x] PromptTemplate
    - [x] DebateArchive

### 2.2 Web Service (Gradio)
- [x] 建立 `web/Dockerfile`
- [x] 建立 `web/requirements.txt` (Gradio, Requests, etc.)
- [x] 建立 `web/app.py` (Basic Gradio layout)

### 2.3 Worker Service (Celery)
- [x] 建立 `worker/Dockerfile`
- [x] 建立 `worker/requirements.txt`
- [x] 建立 `worker/celery_app.py` (Celery configuration)
- [x] 建立 `worker/tasks.py` (Basic task definitions)

## 3. 核心功能實作 (Core Implementation)
### 3.1 工具整合 (Tool Integration)
- [x] 整合現有 Adapters (`adapters/`) 到 Worker```
- [x] 實作 `ToolRegistry` 機制 (SDD 7.1.1)
  - [x] 基本的工具註冊、獲取與列表功能
  - [x] 基於 JSON Schema 的參數驗證
  - [x] 工具調用快取機制 (Cache)
  - [x] 速率限制 (Rate Limiting)
  - [x] 錯誤映射 (Error Mapping)
```- [x] 實作 Worker 調用邏輯 (SDD 7.1.12)

### 3.2 智能體與辯論邏輯 (Agent & Debate Logic)
- [x] 實作主席 (Chairman) 賽前分析邏輯 (SDD FR-003)
- [x] 實作辯論循環邏輯 (SDD FR-004)
  - [x] Agent 發言與工具調用
  - [x] Redis Evidence Board 交互
  - [x] 主席總結

### 3.3 API 實作
- [x] 實作 `/api/v1/debates` (Create, Get, Stream)
- [x] 實作 `/api/v1/agents` (CRUD)
- [x] 實作 `/api/v1/tools` (Test, List)

## 4. 前端開發 (Frontend Development)
- [x] 實作辯論大廳 (Debate Lobby)
- [x] 實作思考流視覺化 (Thinking Stream)
- [x] 實作工具管理介面 (Tool Registry UI)
- [x] 實作歷史復盤介面 (Replay)

## 5. 測試與驗收 (Testing & Acceptance)
- [x] 驗證 Docker Compose 啟動 (AC-001)
- [x] 測試 API 端點
- [x] 測試 Celery 任務執行
- [x] 端對端測試 (E2E) - 完整辯論流程

## 6. 文件與維護 (Documentation & Maintenance)
- [ ] 更新 README.md
- [ ] 記錄 API 文件 (OpenAPI)
