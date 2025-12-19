# TEJ 空數據現象分析與解決方案

## 1. TEJ 回傳空數據 (`[]`) 是合理的嗎？

答案是：**在特定情境下是合理的 (Technical Correctness)，但對 AI Agent 而言是致命的 (Operational Failure)。**

### ✅ 合理的情境 (Expected Empty)
1.  **非交易日 (Non-Trading Days)**
    *   查詢日期是週六、週日或國定假日。
    *   TEJ 嚴格遵守交易日曆，當天無交易即無數據。
2.  **資料庫更新延遲 (Data Lag)**
    *   TEJ 通常在交易日當晚 18:00-20:00 更新收盤數據。
    *   若在盤中 (09:00-13:30) 查詢「當日」股價，會回傳空值。
3.  **查詢未來日期 (Future Dates)**
    *   日誌顯示 Agent 嘗試查詢 `2025-12-13`，若資料庫只更新到 `2024` 年底，必然回傳空值。

### ❌ 異常的情境 (Unexpected Empty)
1.  **日期範圍過大 (Date Span Too Large)**
    *   TEJ API 有限制，若一次查詢超過 1 年的日資料，可能會直接回傳空值並附帶 `warn:date_span_too_large`。
    *   Agent 往往忽略 Warning，只看到 `data: []` 於是產生幻覺。
2.  **參數錯誤**
    *   股票代碼格式錯誤 (如 `2330` vs `2330.TW`)。

---

## 2. 我們的解決方案 (Robust Pricing Utility)

針對上述問題，我們在 **Phase 7** 實作了多層防護網：

### A. 針對「非交易日/假日」
> **解決方案**: `PriceProofCoordinator` 的 **Lookback Window**

當查詢特定日期 `T` 時，協調器不會只查 `T`，而是查詢 `[T-5, T]` 的範圍，並取**最新一筆**資料。
*   **效果**: 即使 Agent 查了週日，系統會自動回傳週五的收盤價，避免空值。

### B. 針對「資料缺失/延遲」
> **解決方案**: **Waterfall Fallback (多源備援)**

當 TEJ (Primary) 回傳空值時，系統自動觸發備援：
1.  嘗試 **TWSE (官方月報表)**：驗證是否為官方數據問題。
2.  嘗試 **Yahoo Finance (外部即時)**：Yahoo 通常有即時盤中報價，可填補 TEJ 的空窗期。

### C. 針對「日期範圍過大」
> **解決方案**: **ToolError Guard (Adapter 層)**

在 `adapters/tej_adapter.py` 中，我們新增了檢查邏輯：
*   若偵測到 `date_span_too_large` 警告，直接拋出 `ToolRecoverableError`。
*   **效果**: 強制中斷 Agent 的思考，並提示：「日期範圍過大，請縮小至 90 天以內」。

### D. 針對「Agent 幻覺」
> **解決方案**: **Prompt Engineering (Prompt 層)**

在 `worker/debate_cycle.py` 中注入強力提示：
*   `💡 重要提示：若 tej.* 回傳空資料，請立即嘗試 yahoo.stock_price...`
*   **效果**: 教導 Agent 在遇到空值時的標準作業程序 (SOP)，而不是編造理由。

---

## 3. 結論

TEJ 回傳空數據本身反映了資料庫的真實狀態，但為了讓 AI 辯論順利進行，我們必須在中間層 (Middleware) 進行處理。透過 **Lookback**、**Fallback** 與 **Error Handling**，我們已將「合理的空數據」轉化為「可用的分析資訊」。