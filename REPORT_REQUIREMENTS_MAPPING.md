# 投資研究報告需求映射分析

## 目標
產出包含九大章節的標準化投資研究報告。

## 工具映射表

| 章節 | 需求內容 | 主要工具 (Primary) | 備援/補充 (Secondary) | 缺口/備註 |
| :--- | :--- | :--- | :--- | :--- |
| **A. 封面** | 基本資訊 | `tej.company_info`, `chinatimes.stock_rt` | `yfinance.stock_info` | |
| | 關鍵圖表 | `tej.stock_price` (K線/Vol), `tej.foreign_holdings` | `chinatimes.stock_kline` | 需輸出數據點供繪圖 |
| **1. 概述** | 簡介/業務 | `tej.company_info` | `searxng.search` | |
| **2. 產品** | 產品/營收比 | `tej.company_info` | `searxng.search` | TEJ 可能無細項營收比重 |
| | 生產流程/鏈 | `internal.industry-tree` (需啟用) | `searxng.search` | 圖形需用文字描述 |
| **3. 產業** | 趨勢/供需 | `searxng.search` | | 高度依賴搜尋與總結 |
| | 競爭分析 | `chinatimes.sector_info` | `searxng.search` | |
| **4. 指標** | 持股變化 | `tej.foreign_holdings`, `tej.institutional_holdings` | | 董監持股需確認工具 |
| | PE/PB/營收 | `tej.stock_price`, `tej.monthly_revenue` | `chinatimes.financial_ratios` | |
| **5. 同業** | 競爭者數據 | `chinatimes.sector_info` -> loop `tej.financial_summary` | | 需多重調用 |
| **6. 財務** | 三表/比率 | `chinatimes.financial_ratios`, `chinatimes.balance_sheet`, `chinatimes.income_statement`, `chinatimes.cash_flow` | `tej.financial_summary` | 數據極為豐富 |
| **7. 股權** | 十大股東 | **(MISSING)** | `searxng.search` | 需依賴搜尋 |
| | 董監/經理人 | `internal.get_key_personnel` (需啟用) | `tej.company_info` (僅主要) | |
| **8. 介紹** | 沿革/關係 | `internal.corporate_relationships` (需啟用) | `searxng.search` | |
| **9. 新聞** | 近期報導 | `chinatimes.stock_news` | `searxng.search` | |

## 待補強工具 (Internal Tools -> Agent Tools)
以下 Internal API 需註冊為 Agent 可用的 Tool：
1. `internal.get_industry_tree` (獲取產業鏈上下游)
2. `internal.get_key_personnel` (獲取董監事/經理人)
3. `internal.get_corporate_relationships` (獲取關係企業)

## 報告生成策略
1. **數據獲取**: Agent 需依序調用上述工具，將原始數據暫存。
2. **圖表處理**: Agent 輸出 JSON 格式的數據 (e.g. `{"chart": "revenue", "data": [...]}`)，前端負責渲染。
3. **文本生成**: Agent 依據 Markdown 模板填充分析內容。