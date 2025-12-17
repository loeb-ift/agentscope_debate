# 題目鎖定機制設計 ("聖旨"系統)

為了徹底解決 Agent 在辯論過程中迷失焦點或反問用戶的問題，我們將實作一套強制的 **Topic Locking (題目鎖定)** 機制。

## 核心概念

**「聖旨 (The Decree)」**：由主席在賽前分析階段產生的**不可變上下文對象 (Immutable Context Object)**。
包含：
1.  **Subject (主體)**: 具體的分析對象（如：台積電 2330.TW）。
2.  **Scope (範圍)**: 時間（2024 Q4）、指標（股價、毛利率）。
3.  **Core Question (核心問題)**: 辯論要解決的唯一問題。

## 實作架構

### 1. 主席端 (Legislature)
*   **職責**: 在 `pre_debate_analysis` 結束時，產出明確的 `decree` 物件。
*   **修改**: 更新 `worker/chairman.py`，確保輸出的 JSON 包含 `step00_decree` 欄位。

### 2. 系統端 (Executive)
*   **職責**: 將 `decree` 廣播並注入到所有 Agent。
*   **修改**: 
    *   `worker/debate_cycle.py`: 解析主席的 `decree`，並將其存儲為 `self.topic_decree`。
    *   `api/prompt_service.py`: 修改 `compose_system_prompt`，新增 `decree` 參數，將其渲染為 System Prompt 的**置頂區塊**。

### 3. Agent 端 (Compliance)
*   **職責**: 每次發言前「複誦」或隱式遵守聖旨。
*   **修改**: `base_contract.yaml` 新增條款：「必須遵守 System Context 定義的 Subject，不得要求外部澄清」。

## Prompt 注入範例

```markdown
# 🔔 DEBATE CONTEXT (IMMUTABLE)
This is the "Decree" from the Chairman. You MUST align with this context.

- **Target Subject**: 敦陽科技 (2480.TW)
- **Timeframe**: 2024 Q4 (Data available up to 2024-12-31)
- **Core Question**: 財報公布對股價的具體影響？

[CONSTRAINT]: Do NOT ask the user for the company name or code. It is provided above.
```

## 執行計畫

1.  **Update PromptService**: 支援 `decree` 注入。
2.  **Update Chairman**: 確保產出 `step00_decree`。
3.  **Update DebateCycle**: 傳遞 `decree` 至所有 Agent。