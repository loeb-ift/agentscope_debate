# 多代理研究系統（MARS）V2 優化計畫 (Simplified & Integrated)

本計畫旨在實現 [Anthropic MARS 架構](https://www.anthropic.com/engineering/multi-agent-research-system)，利用其嚴格的 **Artifact 產出** 機制來「補強」現有的 AgentScope 辯論系統 (V1)。

## 1. 系統架構 (Enhanced V1)

將 MARS V2 視為 V1 系統的一個 **「深度研究引擎 (Research Engine)」**。

*   **V1 (Debate Cycle)**: 負責辯論流程控制、角色扮演、發言。
*   **V2 (MARS Engine)**: 負責在 Agent 發言前，進行 **結構化、多步驟的證據蒐集**。

## 2. V2 核心組件 (The MARS Stack)

V2 核心邏輯位於 `mars/` 資料夾中，與 V1 共用資料庫與 Celery Worker：

### 2.1 Artifacts (標準化產出)
*   **路徑**: `mars/types/artifact.py`
*   **定義**:
    *   `EvidenceDoc`: 來自工具的原始數據。
    *   `Claim`: 經過分析的論點或主張。
    *   `ReportSection`: 最終報告的章節。
    *   `Plan`: 包含 Task Graph 的計畫物件。

### 2.2 Roles (角色)
*   **Planner (`mars/agents/planner.py`)**: 負責將 User Query 拆解為 Task Graph。
*   **Coordinator (`mars/core/coordinator.py`)**: 狀態機，負責調度 Task 的執行與狀態流轉。
*   **Verifier (`mars/agents/verifier.py`)**: 獨立驗證者，檢查 Artifact 的品質。

## 3. 實作路線圖 (Roadmap)

### Phase 1: Infrastructure & API Routing (基建整合) ✅ Done
- [x] 建立 `mars/`, `web_v2/` 目錄結構。
- [x] **API 路由整合**: 修改 `api/main.py`，引入 `mars.api` 並掛載於 `/api/v2` 前綴。
- [x] **Worker 整合**: 確保 Celery Worker 能同時處理 V1 `run_debate_cycle` 與 V2 `run_mars_task`。

### Phase 2: The MARS Engine (核心引擎) ✅ Done
- [x] 實作 `Coordinator` 狀態機。
- [x] 實作 `Planner` 邏輯。
- [x] 實作 `Executor` 與工具封裝 (`MarsToolWrapper`)。
- [x] **驗證**: `verify_mars_v2.py` 確認能產出 12 個 Artifacts。

### Phase 3: Frontend V2 (可視化) ✅ Done
- [x] 建立 `web_v2` (Express) 專案。
- [x] 實作 `task.html` 任務監控與 Artifact 檢視器。

### Phase 4: V1 Reinforcement (後端邏輯替換) 🚧 To Do
- [ ] **目標**: 保持前端 (Gradio) 不變，將後端 Agent 的思考邏輯替換為 MARS V2 引擎。
- [ ] **修改 `worker/debate_cycle.py`**:
    - 在 `_agent_turn_async` 中，不再直接調用 LLM 生成發言。
    - 改為啟動 `Coordinator`，針對辯題進行深度研究 (Plan -> Execute)。
    - 將 `Coordinator` 產出的 Evidence Artifacts 整理為 Context。
    - 最後再讓 LLM 根據這些 Evidence 生成高品質的辯論發言。