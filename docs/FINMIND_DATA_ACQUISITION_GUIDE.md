# FinMind 數據採集指南 (FinMind Data Acquisition Guide)

本指南說明如何使用 FinMind 進行台股程式化數據採集, 以驅動精確的財務審計引擎。

## 1. 核心數據表 (The Big Five)

系統透過 `finmind.data_loader` 提供以下五類核心數據：

### A. 財務報表 (TaiwanStockFinancialStatements)
*   **用途**: 獲取營收、毛利、EBIT、淨利、總資產、總負債等基礎數據。
*   **引擎映射**: 自動轉換為 MetricsEngine 所需的年度/季度輸入。

### B. 現金流量表 (TaiwanStockCashFlowsStatement)
*   **用途**: 精確計算自由現金流 (FCF) 與現金轉化率。
*   **監控項**: 營運現金流 vs. 淨利 (盈餘品質審計)。

### C. 財務比率 (TaiwanStockFinancialRatios)
*   **用途**: 直接獲取 ROE、ROA、流動比、速動比與負債比率。
*   **基準**: 用於快速判斷企業在產業中的競爭地位。

### D. 股利資訊 (TaiwanStockDividend)
*   **用途**: 獲取歷史配息與股利支付率。
*   **估值**: 支持股利折現模型 (DDM) 的驗證。

### E. 月營收 (TaiwanStockMonthRevenue)
*   **用途**: 追蹤最新的營運動能, 偵測營收 YOY 拐點。

## 2. 數據獲取演算法

智能體遵循以下程式化流程：
1.  **自動 Pivot**: 將 FinMind 的 Long-format 數據（type/value 結構）自動轉化為以日期為 Index 的實體表。
2.  **完整性檢查**: 核對營收與淨利是否齊備, 否則觸發「數據缺失補償」。

## 3. 系統整合地位
FinMind 被定義為 **Tier-1 程式化數據源**, 其權威性與 MOPS 官方數據對等, 用於大規模歷史回測與統計審計。
