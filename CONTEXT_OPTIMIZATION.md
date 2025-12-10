# 📉 上下文長度優化策略 (Context Optimization Strategy)

在 LLM 應用中，Context Window 是稀缺且昂貴的資源。本專案採用了多層次的策略來節省 Token，確保在長對話（多輪辯論）中不會發生溢出或失憶。

## 1. 現有機制 (Current Implementation)

### A. 歷史壓縮 (History Compression) 🗜️
*   **機制**：`worker/debate_cycle.py` 中的 `_get_compact_history`。
*   **邏輯**：
    *   將辯論歷史分為 **「近期區 (Recent)」** 與 **「封存區 (Archive)」**。
    *   僅保留最近 **3 條** 完整對話在 Context 中。
    *   更早的對話會被送入 LLM 進行摘要，壓縮成一段 `compressed_history`。
*   **效益**：隨著辯論輪次增加，Context 增長呈線性緩慢增長（僅摘要變長），而非指數級暴漲。

### B. 工具輸出截斷 (Tool Output Truncation) ✂️
*   **機制**：
    *   **網頁抓取** (`WebFetchAdapter`)：限制抓取的內容長度為 5000 字元。
    *   **證據報告** (`collected_evidence`)：當 Agent 超時回傳報告時，每筆工具結果僅保留前 **200 字元** 的預覽。
    *   **日誌顯示**：前端 SSE 串流中的日誌也會進行截斷，避免傳輸過大封包。
*   **效益**：防止爬蟲抓到數萬字的網頁或財報直接塞爆 Context。

### C. 結構化數據 (Structured Data) 📊
*   **機制**：TEJ 等金融工具回傳的是精簡的 JSON 格式（去除無用 HTML/CSS），只包含數據欄位。
*   **效益**：高密度的資訊表達，減少無效 Token。

---

## 2. 建議優化方向 (Future Optimization)

若需要進一步壓縮，可考慮以下技術：

### A. 精確 Token 計算 (Tokenizer Integration)
*   **現狀**：目前使用 `len(string)` 來估算長度，對於中文來說不夠精確（中文 Token/Char 比率不同於英文）。
*   **建議**：引入 `tiktoken` (OpenAI) 或 HuggingFace Tokenizer，根據實際 Token 數來觸發壓縮，而非訊息條數。

### B. 檢索增強生成 (RAG for History)
*   **邏輯**：不再將「摘要」全部放入 Context。
*   **做法**：將所有歷史發言存入向量資料庫 (Vector DB)。當 Agent 發言時，僅檢索與「當前話題」相關的前 N 條歷史記錄。
*   **效益**：將 Context 佔用降至最低，且能回憶起很久以前的具體細節（如果相關的話）。

### C. 角色專屬視角 (Role-Specific Context)
*   **邏輯**：並非所有 Agent 都需要全知視角。
*   **做法**：
    *   **正方**：主要看到反方的「論點」，而不需要看到反方的「工具調用過程」。
    *   **總結員**：只看到各方的「最終發言」，忽略中間的思考過程。
*   **效益**：大幅減少雜訊，提升 Agent 專注度。