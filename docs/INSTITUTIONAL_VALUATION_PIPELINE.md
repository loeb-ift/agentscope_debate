# 機構級自動化估值管線 (Institutional Valuation Pipeline)

本文件描述系統如何整合權威數據源、純 Python 計算引擎與 AI 審計邏輯，以產出具備「物理防禦」與「商業直覺」的專業財務報告。

## 1. 數據獲取鏈 (AUTHORITATIVE FETCHING)
系統遵循 **「權威優先、先大後小」** 的數據獲取原則：
*   **美股**: 透過 `sec_edgar_tool.py` 直接從 **SEC EDGAR XBRL JSON API** 獲取經過審計的 Tag。
*   **台股**: 模擬 **MOPS (公開資訊觀測站)** 流程，優先抓取「三大報表」大項數字，並根據金額佔比自動追蹤「財報附註」。

## 2. 雙軌計算引擎 (DUAL ENGINE ARCHITECTURE)

### A. 數學精確層 (`MetricsEngineDCF_AI`)
負責所有「不可妥協」的硬性數學運算：
*   **EVA (經濟附加價值)**: 計算 NOPAT 與資本成本的差額。
*   **均值回歸與風險折扣**: 
    *   自動計算 **Persistence Score**。
    *   當數據缺失或 ROIC 波動過大時，自動執行 **Terminal Value Discount (15-20%)**。
*   **多情境 DCF**: 產出 Bear/Base/Bull 三種受約束的折現模型。

### B. 智能解讀層 (`AdvancedFinancialReader`)
負責將枯燥的數字轉化為商業趨勢：
*   **趨勢檢測**: 自動標註 ↑/↓/→ 變化。
*   **白話解讀**: 如「產品好不好賺 (毛利率)」、「口袋裡的現金 (FCF)」。
*   **行業對比**: 自動標註與產業基準的偏離度。

## 3. 三階段執行流程與保險絲 (THE 3-STEP CHAIN)

1.  **Phase 1: 數據事實**: `Quant Analyst` 驅動 Python 引擎產出數學事實。
2.  **Phase 2: 語義審計**: `Researcher` 偵測「敘事偏差 (Narrative Deviation)」，檢查新聞是否與引擎指標脫鉤。
3.  **Phase 3: 綜合裁決**: `Chairman` 確保流程通過 **ROIC Gate**，產出具備明確「決策門檻 (Trigger Points)」的最終報告。

## 4. 退化模式與透明度 (DEGRADED MODE)
當權威數據缺失時，系統會：
1.  自動切換至 `[DEGRADED MODE]`。
2.  由 AI 基於片段數據進行邏輯推論。
3.  自動在最終估值中加入 **10% 數據風險折價** 並顯著標註風險。

---
本管線旨在確保 AI 在財務分析中不再是「幻覺來源」，而是具備專業數據支撐的「高效率審計員」。
