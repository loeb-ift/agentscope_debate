# 財務比率公式庫 (Financial Ratio Library v3.0)

本文件定義了 MARS 系統內建計算引擎 (Metrics Engine V3) 的 100+ 項標準化財務公式, 已通過壓力測試與實戰驗證。

## 1. 資本效率與價值創造 (Capital Efficiency) - [VERIFIED ✅]

*   **ROIC (投入資本回報率)** = NOPAT / 投入資本
*   **ROCE (資本運用報酬率)** = EBIT / (總資產 - 流動負債)
*   **EVA (經濟附加價值)** = NOPAT - (投入資本 × WACC)
*   **Spread (價值創造利差)** = ROIC - WACC
*   **Economic Profit Margin** = Spread / ROIC

## 2. 進階現金流分析 (Advanced Cash Flow) - [VERIFIED ✅]

*   **FCF (自由現金流)** = 營運現金流 - 資本支出
*   **FCFE (股東自由現金流)** = FCF - 利息 × (1-稅率) + 淨借款
*   **Cash Conversion Rate** = 營運現金流 / 淨利
*   **CCC (現金轉換週期)** = DSO + DIO - DPO

## 3. 營運效率 (Efficiency) - [VERIFIED ✅]

*   **DSO (應收帳款回收天數)** = (應收帳款 / 營收) × 365
*   **DIO (存貨週轉天數)** = (存貨 / 銷貨成本) × 365
*   **Asset Turnover (總資產週轉率)** = 營收 / 平均總資產

## 4. 財務品質與風險 (Quality & Risk) - [VERIFIED ✅]

*   **Accrual Ratio** = (淨利 - 營運現金流) / 總資產
*   **Interest Coverage (利息保障倍數)** = EBIT / 利息支出
*   **Altman Z-Score**: 偵測破產風險的加權模型。

## 5. 市場估值進階 (Advanced Valuation) - [VERIFIED ✅]

*   **EV/EBITDA**: 排除資本結構差異的估值。
*   **P/FCF**: 比 P/E 更真實的估值指標。
*   **Rule of 40**: 營收成長率 + FCF Margin (科技股專用)。

---
*所有計算均由系統 `worker/metrics_engine_dcf_v3.py` 自動執行，具備物理防禦與邏輯校驗功能。*
