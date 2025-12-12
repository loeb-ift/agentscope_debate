# 本專案的記憶與快取機制設計 (v3.0 - 海馬迴架構版)

本文件說明本專案升級後的「海馬迴記憶架構 (Hippocampal Memory Architecture)」，該架構整合了短期感知、長期知識庫與自動鞏固機制，旨在為多智能體（Multi-Agent）辯論系統提供集體智慧與高效協作能力。

## 核心架構：海馬迴 (Hippocampal Memory)

我們引入了 `HippocampalMemory` 類別作為記憶系統的核心，模仿人腦海馬迴的功能，負責將短期的感知輸入（Sensory Input）轉化為長期的穩定記憶（Long-term Memory）。

### 三層記憶結構

1.  **感知層與工作記憶 (Working Memory)**
    *   **介質**：Redis (In-memory Cache)
    *   **角色**：短期緩衝區，具備高頻讀寫能力與 TTL (Time-To-Live) 自動過期機制。
    *   **功能**：
        *   **感知攔截 (Sensory Gating)**：當 Agent 試圖調用工具時，系統優先攔截請求。
        *   **快取命中**：若相同參數的工具調用在短期內已發生過（由任何 Agent），直接返回 Redis 中的結果，節省 API 成本與時間。
        *   **即時寫入**：若無快取，執行工具後，將結果（輸入+輸出）即時存入工作記憶，並初始化存取計數 (`access_count=1`)。

2.  **長期記憶 (Long-term Memory)**
    *   **介質**：Qdrant (Vector Database)
    *   **角色**：永久知識庫，儲存經過驗證或高頻使用的高價值資訊。
    *   **功能**：
        *   **統一儲存**：取代原先分散的 `ReMeTask/Tool` 集合，統一存放於 `hippocampus_{debate_id}` 集合中。
        *   **語義檢索**：支援 Embedding 向量相似度搜尋。

3.  **索引層 (Indexing Layer)**
    *   為了確保長期記憶能被精準檢索，我們在 Qdrant Payload 中建立了多維度索引：
    *   **Semantic (語義)**：意圖匹配 (Vector)。
    *   **Temporal (時間)**：資料產生的時間戳，支援 `Date Range` 查詢。
    *   **Source (來源)**：記錄 Agent ID 與 Tool Name，支援來源過濾。

### 記憶作用範圍 (Memory Scope)

為了確保辯論的獨立性與效率，海馬體具有明確的作用範圍：

1.  **場次範圍 (Session Scope)**：**Per-Debate 隔離**。
    *   每個辯論場次 (`debate_id`) 擁有獨立的 Redis 空間與向量集合 (`hippocampus_{debate_id}`)。
    *   不同場次間的記憶互不相通，確保每場辯論從乾淨的狀態開始（除非透過 Task LTM 查詢歷史案例）。

2.  **參與者範圍 (Participant Scope)**：**Session 內全域共享**。
    *   同一場辯論內的所有 Agent（正方、反方、主席）共享同一個海馬體實例。
    *   **效益**：正方查過的資料（如台積電股價），反方可直接取用（Cache Hit），極大化提升效率並減少重複的 API 開銷。

3.  **資料範圍 (Data Scope)**：**工具執行結果 (Tool Outputs)**。
    *   專注於快取客觀事實與查詢結果。
    *   **負面快取 (Negative Caching)**：系統**會**快取「空結果」或「錯誤結果」。若某個 Agent 搜尋不存在的公司（如 "3444"）返回空值，此結果會被寫入記憶。後續 Agent 再次搜尋時將直接命中快取並得知「無結果」，避免陷入重複執行無效工具的邏輯迴圈。

---

## 關鍵機制：記憶鞏固 (Consolidation)

記憶不再是「寫入即永久」，而是需要經過篩選。

*   **觸發條件**：
    *   **閾值觸發**：當工作記憶中的某條資訊被不同 Agent 或多次存取（`access_count >= 2`），視為重要資訊。
    *   **週期性觸發**：每輪 (Round) 辯論結束時，系統自動掃描工作記憶。
*   **執行動作**：
    *   將符合條件的短期記憶項目提取出來。
    *   生成摘要與向量 Embedding。
    *   寫入 Qdrant 長期記憶庫，並標記為 `consolidated`。

---

## Agent 協作與新工具

為了讓 Agent 能主動利用這個集體大腦，我們新增了以下機制：

1.  **新工具：`search_shared_memory`**
    *   **功能**：允許 Agent 主動查詢共享記憶庫。
    *   **情境**：「在調用 `tej.stock_price` 之前，先查查 `search_shared_memory` 看有沒有隊友已經查過台積電上個月的股價。」
    *   **參數**：`query` (語義問題), `filter_tool` (可選，指定來源工具)。

2.  **Prompt 引導**
    *   在 `debater.system_instruction` 與 `debater.tool_instruction` 中加入了明確指令，強烈建議 Agent 在進行耗時調查前先查詢共享記憶，避免重複勞動。

3.  **延長申請攔截 (Extension Interception)**
    *   當 Agent 申請延長調查（`request_extension`）時，系統會**強制**先查詢海馬迴記憶。
    *   若系統發現共享記憶中已有 Agent 所需的資訊（基於申請理由匹配），將**自動駁回**申請，並直接提供相關記憶內容。
    *   這充當了「知識守門員」，防止 Agent 因為不知道隊友已經查過而浪費資源。

---

## 舊版相容性說明

*   **ReMe* 類別**：原有的 `ReMePersonalLongTermMemory`, `ReMeTaskLongTermMemory` 等類別保留用於特定用途（如個人偏好），但核心的工具結果儲存已由 `HippocampalMemory` 接管。
*   **LLM 語意快取**：`worker/llm_utils.py` 中的 LLM 回應快取機制保持不變，與海馬迴並行運作（前者快取「思考」，後者快取「感知/工具」）。

---

## 維運建議

*   **Redis 監控**：關注 Working Memory 的 Key 數量與 TTL 設定，確保記憶體不溢出。
*   **Qdrant 容量**：長期記憶會隨著辯論次數增加而累積，建議定期（如每季）對舊的 `hippocampus_{id}` 集合進行歸檔或清理。
*   **閾值調整**：可根據實際運作狀況調整 `consolidation_threshold`。若垃圾資訊太多，提高閾值；若有價值資訊遺失，降低閾值。
