# 現有數據來源盤點與 EDA 整合分析

## 📊 系統現有工具總覽

### 已註冊工具統計

根據 `tool_registry.py` 和 `api/main.py` 的分析：

| 工具類別 | 數量 | 主要提供商 | 狀態 |
|---------|------|-----------|------|
| **財務數據** | 40+ | ChinaTimes, TEJ, Yahoo | ✅ 可用 |
| **搜尋工具** | 4 | Google, SearXNG, DuckDuckGo | ✅ 可用 |
| **內部工具** | 3 | Internal Entity | ✅ 可用 |
| **MCP 工具** | N | Alpha Vantage | ⚠️ 條件可用 |
| **EDA 工具** | 2 | ODS, Chairman EDA | ✅ 新增 |

---

## 🔍 詳細數據來源分析

### 1. ChinaTimes Suite (12 個工具)

#### 1.1 股價與市場數據

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `chinatimes.stock_rt` | 即時股價 | OHLCV + 成交量 | ✅ **高優先級** |
| `chinatimes.stock_kline` | K 線歷史數據 | 日 K 線 | ✅ **高優先級** |
| `chinatimes.market_index` | 市場指數 | 大盤指數 | ✅ 中優先級 |
| `chinatimes.market_rankings` | 市場排行 | Top 10 | ⚠️ 低優先級 |
| `chinatimes.sector_info` | 產業資訊 | 產業分類 | ✅ 中優先級 |

**數據範例** (`chinatimes.stock_kline`):
```json
{
  "data": [
    {
      "date": "2024-12-18",
      "open": 950.0,
      "high": 960.0,
      "low": 945.0,
      "close": 955.0,
      "volume": 25000000,
      "change": 5.0,
      "change_pct": 0.53
    }
  ]
}
```

#### 1.2 財務報表數據

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `chinatimes.stock_fundamental` | 基本面檢查 | 營收、EPS、本益比 | ✅ **高優先級** |
| `chinatimes.financial_ratios` | 財務比率 | ROE, ROA, 負債比 | ✅ **高優先級** |
| `chinatimes.balance_sheet` | 資產負債表 | 資產、負債、權益 | ✅ 中優先級 |
| `chinatimes.income_statement` | 損益表 | 營收、毛利、淨利 | ✅ 中優先級 |
| `chinatimes.cash_flow` | 現金流量表 | 營業/投資/融資現金流 | ✅ 中優先級 |

**數據範例** (`chinatimes.stock_fundamental`):
```json
{
  "Code": "2330",
  "Name": "台積電",
  "SectorName": "半導體業",
  "EPS": 8.5,
  "ROE": 25.6,
  "PERatio": 22.5,
  "DividendYield": 2.8,
  "MarketCap": 25000000000000
}
```

**數據範例** (`chinatimes.financial_ratios`):
```json
{
  "data": {
    "pe_ratio": 22.5,
    "pb_ratio": 5.2,
    "roe": 25.6,
    "roa": 15.3,
    "debt_ratio": 35.2,
    "current_ratio": 1.8,
    "gross_margin": 52.3,
    "net_margin": 38.5
  }
}
```

#### 1.3 新聞與資訊

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `chinatimes.news_search` | 新聞搜尋 | 新聞標題、內容 | ❌ 不適用 |
| `chinatimes.stock_news` | 個股新聞 | 個股相關新聞 | ❌ 不適用 |

---

### 2. TEJ Suite (23 個工具)

#### 2.1 公司基本資料

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `tej.company_info` | 公司資訊 | 公司名稱、產業、代碼 | ✅ 高優先級 |
| `tej.stock_price` | 股價數據 | OHLCV | ✅ **高優先級** |
| `tej.monthly_revenue` | 月營收 | 每月營收數據 | ✅ **高優先級** |

**數據範例** (`tej.stock_price`):
```json
{
  "data": [
    {
      "coid": "2330",
      "mdate": "2024-12-18",
      "close_d": 955.0,
      "open_d": 950.0,
      "high_d": 960.0,
      "low_d": 945.0,
      "vol": 25000000
    }
  ]
}
```

**數據範例** (`tej.monthly_revenue`):
```json
{
  "data": [
    {
      "coid": "2330",
      "year": 2024,
      "month": 11,
      "revenue": 250000000000,
      "revenue_yoy": 15.2,
      "revenue_mom": 3.5
    }
  ]
}
```

#### 2.2 籌碼數據

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `tej.institutional_holdings` | 法人持股 | 三大法人持股 | ✅ 中優先級 |
| `tej.margin_trading` | 融資融券 | 融資餘額、融券餘額 | ✅ 中優先級 |
| `tej.foreign_holdings` | 外資持股 | 外資持股比例 | ✅ 中優先級 |

#### 2.3 財務數據

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `tej.financial_summary` | 財務摘要 | 綜合財務指標 | ✅ **高優先級** |
| `tej.financial_summary_quarterly` | 季度財務摘要 | 季度財務數據 | ✅ **高優先級** |
| `tej.financial_cover_cumulative` | 累計財務數據 | 年度累計 | ✅ 中優先級 |
| `tej.financial_cover_quarterly` | 季度財務數據 | 季度數據 | ✅ 中優先級 |

#### 2.4 基金數據 (10+ 工具)

**評估**: 對股票 EDA 不適用，可忽略

---

### 3. Yahoo Finance / TWSE

| 工具名稱 | 功能 | 數據類型 | EDA 可用性 |
|---------|------|---------|-----------|
| `yfinance.stock` | Yahoo Finance 股價 | OHLCV | ✅ **當前使用** |
| `twse.stock_day` | 證交所每日股價 | OHLCV | ✅ 備用 |
| `yahoo.price` | Yahoo 價格 | 即時價格 | ✅ 備用 |

---

## 🎯 EDA 整合優先級分析

### Tier 1: 必須整合（高價值、低難度）

| 數據來源 | 工具 | 提供數據 | 整合難度 | 預估工時 |
|---------|------|---------|---------|---------|
| **ChinaTimes** | `stock_fundamental` | EPS, ROE, 本益比 | 低 | 1h |
| **ChinaTimes** | `financial_ratios` | 完整財務比率 | 低 | 1h |
| **TEJ** | `monthly_revenue` | 月營收趨勢 | 中 | 1.5h |
| **TEJ** | `financial_summary_quarterly` | 季度財務 | 中 | 1.5h |

**總工時**: ~5 小時

### Tier 2: 建議整合（高價值、中難度）

| 數據來源 | 工具 | 提供數據 | 整合難度 | 預估工時 |
|---------|------|---------|---------|---------|
| **ChinaTimes** | `stock_kline` | K 線歷史 | 低 | 0.5h |
| **ChinaTimes** | `balance_sheet` | 資產負債表 | 中 | 1h |
| **ChinaTimes** | `income_statement` | 損益表 | 中 | 1h |
| **TEJ** | `institutional_holdings` | 法人持股 | 中 | 1h |

**總工時**: ~3.5 小時

### Tier 3: 可選整合（中價值、高難度）

| 數據來源 | 工具 | 提供數據 | 整合難度 | 預估工時 |
|---------|------|---------|---------|---------|
| **ChinaTimes** | `cash_flow` | 現金流量表 | 中 | 1h |
| **TEJ** | `margin_trading` | 融資融券 | 中 | 1h |
| **TEJ** | `foreign_holdings` | 外資持股 | 中 | 1h |

**總工時**: ~3 小時

---

## 📋 整合策略建議

### 方案 A: 最小可行版本 (MVP)

**整合範圍**: Tier 1 必須整合  
**預估工時**: 5 小時  
**數據覆蓋**:
- ✅ 股價 (Yahoo Finance - 已有)
- ✅ 基本面 (ChinaTimes Fundamental)
- ✅ 財務比率 (ChinaTimes Ratios)
- ✅ 營收趨勢 (TEJ Monthly Revenue)
- ✅ 季度財務 (TEJ Quarterly)

**主席總結能力**:
- 價格分析 ✅
- 基本面評估 ✅
- 估值判斷 ✅
- 營收成長分析 ✅

### 方案 B: 完整版本

**整合範圍**: Tier 1 + Tier 2  
**預估工時**: 8.5 小時  
**額外數據**:
- K 線技術分析
- 完整三大報表
- 籌碼面分析

**主席總結能力**:
- 所有方案 A 能力
- 技術面分析 ✅
- 財務健康度深度分析 ✅
- 籌碼面評估 ✅

### 方案 C: 漸進式整合（推薦）

**階段 1** (2 小時): 基本面
- `chinatimes.stock_fundamental`
- `chinatimes.financial_ratios`

**階段 2** (3 小時): 營收與財務
- `tej.monthly_revenue`
- `tej.financial_summary_quarterly`

**階段 3** (3.5 小時): 完整報表與籌碼
- `chinatimes.balance_sheet`
- `chinatimes.income_statement`
- `tej.institutional_holdings`

**優點**:
- ✅ 每階段可獨立驗證
- ✅ 風險可控
- ✅ 可根據效果調整

---

## 🔧 技術整合方案

### 數據拉取架構

```python
async def _prepare_financial_data(self, symbol: str, debate_id: str) -> dict:
    """
    整合多個數據來源
    
    優先級策略:
    1. ChinaTimes (優先，數據完整且即時)
    2. TEJ (備用，數據權威但可能延遲)
    3. 降級：部分數據缺失時仍繼續
    """
    financial_data = {
        "fundamental": {},
        "ratios": {},
        "revenue": {},
        "quarterly": {},
        "success": False
    }
    
    # 1. 基本面 (ChinaTimes)
    try:
        result = await call_tool("chinatimes.stock_fundamental", {"code": symbol})
        if result.get("success"):
            financial_data["fundamental"] = result["data"]
    except Exception as e:
        print(f"Failed to fetch fundamental: {e}")
    
    # 2. 財務比率 (ChinaTimes)
    try:
        result = await call_tool("chinatimes.financial_ratios", {"code": symbol})
        if result.get("success"):
            financial_data["ratios"] = result["data"]
    except Exception as e:
        print(f"Failed to fetch ratios: {e}")
    
    # 3. 月營收 (TEJ)
    try:
        result = await call_tool("tej.monthly_revenue", {
            "coid": symbol.replace(".TW", ""),
            "opts.limit": 12  # 最近 12 個月
        })
        if result.get("data"):
            financial_data["revenue"] = result["data"]
    except Exception as e:
        print(f"Failed to fetch revenue: {e}")
    
    # 4. 季度財務 (TEJ)
    try:
        result = await call_tool("tej.financial_summary_quarterly", {
            "coid": symbol.replace(".TW", ""),
            "opts.limit": 4  # 最近 4 季
        })
        if result.get("data"):
            financial_data["quarterly"] = result["data"]
    except Exception as e:
        print(f"Failed to fetch quarterly: {e}")
    
    # 判斷是否成功（至少有一個數據源）
    financial_data["success"] = any([
        financial_data["fundamental"],
        financial_data["ratios"],
        financial_data["revenue"],
        financial_data["quarterly"]
    ])
    
    return financial_data
```

### 數據合併策略

```python
def _merge_financial_data(self, df_price: pd.DataFrame, financial_data: dict) -> pd.DataFrame:
    """
    將財務數據合併到股價 DataFrame
    
    策略：
    1. 股價數據：每日
    2. 財務數據：季度/月度
    3. 合併方式：Forward Fill（財務數據向前填充）
    """
    df = df_price.copy()
    
    # 新增財務欄位（從最新數據）
    if financial_data.get("fundamental"):
        fund = financial_data["fundamental"]
        df['eps'] = fund.get('EPS')
        df['roe'] = fund.get('ROE')
        df['pe_ratio'] = fund.get('PERatio')
    
    if financial_data.get("ratios"):
        ratios = financial_data["ratios"]
        df['debt_ratio'] = ratios.get('debt_ratio')
        df['current_ratio'] = ratios.get('current_ratio')
        df['gross_margin'] = ratios.get('gross_margin')
    
    # 營收趨勢（時間序列）
    if financial_data.get("revenue"):
        # 創建月度 DataFrame 並合併
        revenue_df = pd.DataFrame(financial_data["revenue"])
        # ... 時間序列對齊邏輯
    
    return df
```

---

## 📊 預期成果對比

### 當前版本（僅股價）

```markdown
### EDA 自動分析報告

**分析標的**: 2330.TW  
**數據期間**: 120 個交易日  

**價格分析**:
- 平均收盤價：$950.25
- 期間漲跌幅：+12.5%
- 波動率：4.5%
```

### 整合後版本（方案 A - MVP）

```markdown
### EDA 自動分析報告

**分析標的**: 2330.TW (台積電)  
**數據期間**: 120 個交易日 + 最近 4 季財報  

**價格分析**:
- 平均收盤價：$950.25
- 期間漲跌幅：+12.5%
- 波動率：4.5%

**基本面分析**:
- EPS（最近季）：$8.5
- ROE：25.6%
- 產業：半導體業

**財務比率**:
- 本益比：22.5x（產業平均：18.3x）
- 股價淨值比：5.2x
- 負債比率：35.2%（健康）
- 流動比率：1.8（良好）

**營收趨勢**:
- 最近月營收：$2,500 億
- 月增率：+3.5%
- 年增率：+15.2%

**估值評估**:
- 相對產業：偏高 (+23%)
- 成長性：優異
- 財務健康度：良好
- **綜合評估：合理偏高，但成長性支撐估值**
```

---

## 🎯 最終建議

### 立即執行（本次迭代）

**採用方案 C - 階段 1**:
1. 整合 `chinatimes.stock_fundamental`
2. 整合 `chinatimes.financial_ratios`
3. 預估工時：**2 小時**
4. 驗證效果後決定是否繼續

### 理由

1. **風險最低**: 僅 2 個 API，數據格式簡單
2. **價值最高**: 立即提供基本面 + 估值能力
3. **可驗證**: 快速看到效果，決定下一步
4. **不阻塞**: 不影響當前版本運行

### 下一步（視效果決定）

- ✅ 效果好 → 繼續階段 2（營收與季度財務）
- ⚠️ 效果一般 → 優化現有整合
- ❌ 問題多 → 回到僅股價版本

---

## 總結

**現有可用數據**:
- 40+ 財務工具已註冊
- ChinaTimes + TEJ 雙重覆蓋
- 數據完整度高

**建議整合路徑**:
1. **階段 1** (2h): 基本面 + 財務比率
2. **階段 2** (3h): 營收 + 季度財務
3. **階段 3** (3.5h): 完整報表 + 籌碼

**預期提升**:
- 主席總結從「技術分析」→「全面投資建議」
- 決策依據從「單一維度」→「多維度交叉驗證」
- 可信度從「價格趨勢」→「基本面支撐」
