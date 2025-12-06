# 主席智能體 (Chairman Agent) 運作流程與邏輯詳解

本文檔詳細說明了 AI 辯論平台中「主席」角色的運作邏輯，包括賽前分析管線與回合總結機制。

## 1. 賽前分析 (Pre-debate Analysis)

主席在辯論開始前，會執行一個深度的 **7 步驟分析管線**，目的是為整場辯論奠定戰略基礎。

### 觸發時機
當 `DebateCycle.start()` 被調用時，首先執行的就是 `chairman.pre_debate_analysis(topic)`。

### 7 步分析管線邏輯

1.  **步驟 1：題型識別 (Type Classification)**
    *   **邏輯**：分析辯題是「事實型」、「價值型」還是「政策型」。
    *   **目的**：決定辯論的走向（例如：政策型辯題需關注可行性與利弊比較）。

2.  **步驟 2：核心要素提取 (Core Elements Extraction)**
    *   **邏輯**：識別辯題中的關鍵實體：行動主體 (Actor)、行動 (Action)、目標 (Goal) 等。
    *   **目的**：鎖定討論範圍，避免離題。

3.  **步驟 3：因果鏈建構 (Causal Chain Mapping)**
    *   **邏輯**：預測正反雙方可能的邏輯路徑（例如：政策 -> 機制 -> 結果）。
    *   **目的**：找出邏輯漏洞與關鍵斷點。

4.  **步驟 4：子問題分解 (Sub-Questions Breakdown)**
    *   **邏輯**：將大辯題拆解為 5-8 個可驗證的具體子問題（如：技術可行嗎？成本可控嗎？）。
    *   **目的**：引導 Agent 針對具體問題進行攻防，而非空泛議論。

5.  **步驟 5：資料蒐集戰略 (Research Strategy)**
    *   **邏輯**：規劃需要什麼數據（學術報告、統計數據、案例）以及關鍵詞。
    *   **目的**：指導 Agent 如何有效使用工具。

6.  **步驟 6：主席手卡生成 (Chairman Handcard)**
    *   **邏輯**：這是最重要的輸出。匯總上述分析，生成一份包含「正反論證架構」、「關鍵交鋒點」、「引導問題庫」的結構化筆記。
    *   **作用**：此手卡會被傳遞給 `summarize_round`，作為主席評估每輪辯論的標準。

7.  **步驟 7：工具策略映射 (Tool Strategy Mapping)**
    *   **邏輯**：根據需要的數據類型（如最新股價 vs 歷史財報），推薦特定的工具（如 `tej.stock_price` vs `searxng.search`）。
    *   **目的**：優化工具調用的精準度。

### 輸出結果
分析完成後，生成一個 JSON 物件。系統會將 `step6_handcard` 提取出來，作為整場辯論的戰略指導。

---

## 2. 回合總結 (Round Summary)

在每一輪辯論（正反方發言）結束後，主席會進行總結與評價。

### 觸發時機
`DebateCycle._run_round()` 的最後一步調用 `chairman.summarize_round()`。

### 評價邏輯

1.  **輸入數據**：
    *   **本輪發言與證據**：從 Redis (`debate:{id}:evidence`) 獲取本輪 Agent 提交的所有工具調用結果與發言摘要。
    *   **主席手卡 (Handcard)**：使用賽前分析生成的 `step6_handcard`。

2.  **LLM 評估過程**：
    主席會將「本輪實際發言」與「賽前手卡」進行比對，思考以下問題：
    *   **交鋒點檢核**：雙方是否觸及了手卡中預測的「關鍵交鋒點」？還是僅在無關細節上糾纏？
    *   **證據有效性**：提出的證據（來自工具）是否有效支持了其論點？
    *   **引導方向**：根據手卡中的「未解決子問題」，下一輪應該聚焦討論什麼？

3.  **輸出結果**：
    主席發表一段總結性發言，不僅是概括本輪內容，更包含**戰略性引導**（例如：「正方提出了經濟效益的數據，但反方尚未對環境成本做出有效回應，請下一輪反方針對此點進行反駁...」）。

---

## 3. 系統交互圖

```mermaid
sequenceDiagram
    participant User
    participant DebateCycle
    participant Chairman
    participant LLM
    participant Redis

    User->>DebateCycle: Start Debate
    
    rect rgb(240, 248, 255)
    note right of DebateCycle: 賽前分析階段
    DebateCycle->>Chairman: pre_debate_analysis(topic)
    Chairman->>LLM: 7-Step Analysis Prompt
    LLM-->>Chairman: JSON Result (含 Handcard)
    Chairman->>DebateCycle: 返回 Analysis Result
    end

    loop Every Round
        DebateCycle->>DebateCycle: Agent 發言 & 工具調用
        DebateCycle->>Redis: 存儲 Evidence
        
        rect rgb(255, 250, 240)
        note right of DebateCycle: 回合總結階段
        DebateCycle->>Chairman: summarize_round(round, handcard)
        Chairman->>Redis: 讀取本輪 Evidence
        Chairman->>LLM: 評估 Prompt (Handcard + Evidence)
        LLM-->>Chairman: 戰略性總結
        Chairman->>DebateCycle: 發表總結
        end
    end