# ADR-003: Agent Guardrails 設計 (Preventing Tool Looping & Misreasoning)

## Status
Accepted

## Date
2025-12-13

## Context（背景）

LLM 在面對真實世界 API 時，會自然套用「人類常識推理」：
*   無資料 → 公司錯
*   重試 → 換個問法
*   失敗 → 重新確認前提

但金融 API 的實際行為往往違反直覺（例如 TEJ 限制日期跨度否則回傳空值），導致：
*   無限 tool retry
*   公司名稱反覆查詢
*   Step budget 被耗盡

## Decision（架構決策）

採用 **結構性 Guardrails**，而非僅靠 Prompt 運氣。

### 1. Adapter 顯性錯誤策略 (Explicit Error Taxonomy)
**決策：**
*   將隱性 warning 昇級為顯性錯誤 (Exception)
*   明確區分錯誤等級：
    *   `RECOVERABLE`: 可調整參數重試 (如 Rate Limit, Date Span)
    *   `TERMINAL`: 此路徑無解 (如 404, Data Not Found)
    *   `FATAL`: 系統級崩潰 (如 Auth Error)

**理由：**
*   LLM 無法穩定解讀半結構化錯誤或空值回應。

### 2. TEJ 生存指南 (System Prompt Constraints)
**決策：**
System Prompt 中明文規定：
*   日期錯誤 → 只能縮小日期範圍
*   禁止懷疑 `company_id`
*   禁止重複查詢公司名稱

**理由：**
*   將供應商潛規則顯性化，修正 LLM 的錯誤歸因。

### 3. Phase Lock (行為階段鎖)
**決策：**
Agent State 明確區分：`IDENTIFICATION` → `DATA_FETCHING` → `ANALYSIS` → `SUMMARY`

在 `DATA_FETCHING` 階段：
*   禁止呼叫公司搜尋工具 (`internal.search_company`)

**理由：**
*   防止跨階段錯誤行為（已拿到 ID 卻回頭查名字）。

### 4. 失敗模式記憶 (Failure Mode Memory)
**決策：**
*   記錄已發生錯誤類型與解法 `{Agent:Tool:Error:ParamsHash}`
*   同一回合禁止重複嘗試同型錯誤（Circuit Breaker）

**理由：**
*   防止「語義變形的重試」（換個參數名但值一樣，或反覆撞同一牆）。

### 5. Loop Sentinel (鬼打牆偵測)
**決策：**
*   偵測指標：同一 tool + 相同 company_id + 高參數相似度
*   觸發時強制中斷或改策略，並輸出 `[LOOP_DETECTED]` Log

**理由：**
*   從系統層防止模型失控，提供可觀測性。

## Consequences（影響）

**正面：**
*   徹底消除 Agent 鬼打牆
*   Tool 使用行為可預測
*   成本與延遲穩定

**代價：**
*   Agent 自由度降低
*   初期設計需更嚴謹

## Future Work
*   Guardrails 抽象化為可重用模組
*   成功模式回饋（Success Pattern Memory）