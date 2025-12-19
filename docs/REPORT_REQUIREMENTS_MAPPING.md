# 投資研究報告結構與工具映射 (Investment Research Report Mapping)

本文件定義了標準化投資報告的章節結構，以及每個章節應使用的數據來源工具。Report Editor Agent 需嚴格遵循此結構進行內容生成。

## 報告章節定義

### 1. 投資評等 (Investment Rating)
- **內容**: 買進/持有/賣出建議、目標價、潛在漲幅。
- **來源**: 綜合辯論結果、Chairman 總結。
- **工具**: 無 (由 Agent 綜合判斷)。

### 2. 重點摘要 (Key Highlights)
- **內容**: 3-5 點核心投資邏輯摘要。
- **來源**: 辯論雙方最強有力的論點。
- **工具**: 無 (由 Agent 提煉)。

### 3. 基本資料 (Company Profile)
- **內容**: 公司名稱、代碼、成立日期、市值、主要業務、經營團隊、十大股東。
- **工具**:
  - `tej.company_info` (基本資料)
  - `internal.get_key_personnel` (經營團隊) [需新增]
  - `tej.institutional_holdings` (法人持股/十大股東)
  - `tej.foreign_holdings` (外資持股)

### 4. 營運概況 (Operational Overview)
- **內容**: 產品組合 (營收佔比)、銷售區域、生產基地、產能狀況。
- **工具**:
  - `chinatimes.stock_fundamental` (基本面概況)
  - `tej.monthly_revenue` (月營收趨勢)
  - `internal.get_product_mix` (產品組合 - 待實作或從年報解析)
  - `internal.get_production_sites` (生產基地 - 待實作或從年報解析)

### 5. 產業分析 (Industry Analysis)
- **內容**: 產業地位、供應鏈位置 (上/中/下游)、競爭對手比較、產業成長率。
- **工具**:
  - `internal.get_industry_tree` (產業鏈位置)
  - `chinatimes.sector_info` (產業資訊)
  - `chinatimes.market_rankings` (同業排名)
  - `tej.stock_price` (用於計算同業股價表現)

### 6. 財務分析 (Financial Analysis)
- **內容**:
  - 獲利能力 (三率: 毛利率、營益率、淨利率)
  - 成長性 (營收成長率、獲利成長率)
  - 償債能力 (負債比、流動比)
  - 現金流狀況 (OCF, FCF)
- **工具**:
  - `tej.financial_summary` (財務摘要)
  - `chinatimes.stock_kline` (股價走勢)
  - `tej.financial_cover_quarterly` (季財務比率)
  - `tej.financial_cover_cumulative` (累計財務比率)

### 7. 估值分析 (Valuation)
- **內容**: 本益比 (PE)、股價淨值比 (PB)、殖利率 (Yield)、歷史區間比較。
- **工具**:
  - `chinatimes.stock_rt` (即時股價與 PE/PB)
  - `tej.stock_price` (歷史 PE/PB 區間計算)
  - `tej.offshore_fund_dividend` (若為基金)

### 8. 風險分析 (Risk Analysis)
- **內容**: 產業風險、營運風險、財務風險、政策風險。
- **來源**: 反方 (Con Team) 的論點摘要。
- **工具**: 無 (由 Agent 提煉)。

### 9. 投資建議 (Investment Thesis)
- **內容**: 結論、催化劑 (Catalysts)、關注時程。
- **來源**: 綜合辯論結果。

---

## 圖表需求 (Chart Requirements)

Agent 應在對應章節插入 `[CHART_DATA]` 區塊，前端將其渲染為圖表。

1.  **股價走勢圖 (Price History)**
    - 位置: 第 1 章或第 6 章
    - 數據: 日 K 線 (Date, Open, High, Low, Close, Volume)
2.  **營收趨勢圖 (Revenue Trend)**
    - 位置: 第 4 章
    - 數據: 月營收 (Month, Revenue, YoY)
3.  **獲利能力趨勢 (Profitability Trend)**
    - 位置: 第 6 章
    - 數據: 季別三率 (Quarter, GM%, OPM%, NPM%)
4.  **本益比河流圖 (PE Band)**
    - 位置: 第 7 章
    - 數據: 歷史股價與對應 PE 倍數線
