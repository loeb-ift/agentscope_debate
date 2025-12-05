"""
統一的工具配置，供主席和 Agent 使用。
確保所有代理對可用工具有一致的認知。
"""

# 工具列表定義
AVAILABLE_TOOLS = {
    "tej": {
        "category": "TEJ 台股工具",
        "description": "用於台灣股市分析",
        "tools": [
            {
                "name": "tej.stock_price",
                "description": "查詢台股股價數據（開高低收、成交量、報酬率、本益比等）",
                "params": "coid='股票代碼', start_date='YYYY-MM-DD', end_date='YYYY-MM-DD', limit=數量",
                "example": '{"tool": "tej.stock_price", "params": {"coid": "2330", "start_date": "2024-01-01", "end_date": "2024-12-31", "limit": 300}}'
            },
            {
                "name": "tej.company_info",
                "description": "查詢公司基本資料（產業、成立日、董事長、資本額等）",
                "params": "coid='股票代碼'",
                "example": '{"tool": "tej.company_info", "params": {"coid": "2330"}}'
            },
            {
                "name": "tej.monthly_revenue",
                "description": "查詢月營收數據（單月營收、年增率、累計營收等）",
                "params": "coid='股票代碼', start_date='YYYY-MM-DD', end_date='YYYY-MM-DD'",
                "example": '{"tool": "tej.monthly_revenue", "params": {"coid": "2330"}}'
            },
            {
                "name": "tej.institutional_holdings",
                "description": "查詢三大法人買賣超（外資、投信、自營商）",
                "params": "coid='股票代碼', start_date='YYYY-MM-DD', end_date='YYYY-MM-DD'",
                "example": '{"tool": "tej.institutional_holdings", "params": {"coid": "2330"}}'
            },
            {
                "name": "tej.margin_trading",
                "description": "查詢融資融券數據（融資餘額、融券餘額、使用率等）",
                "params": "coid='股票代碼', start_date='YYYY-MM-DD', end_date='YYYY-MM-DD'",
                "example": '{"tool": "tej.margin_trading", "params": {"coid": "2330"}}'
            },
            {
                "name": "tej.financial_summary",
                "description": "查詢財務報表（營收、EPS、ROE、資產負債等）",
                "params": "coid='股票代碼'",
                "example": '{"tool": "tej.financial_summary", "params": {"coid": "2330"}}'
            }
        ]
    },
    "general": {
        "category": "一般工具",
        "description": "用於網頁搜尋和國際股市查詢",
        "tools": [
            {
                "name": "searxng.search",
                "description": "網頁搜尋",
                "params": "q='關鍵字', engines='google cse'",
                "example": '{"tool": "searxng.search", "params": {"q": "台積電 2024 Q4", "engines": "google cse"}}'
            },
            {
                "name": "yfinance.stock_info",
                "description": "國際股票查詢",
                "params": "symbol='股票代碼'",
                "example": '{"tool": "yfinance.stock_info", "params": {"symbol": "TSM"}}'
            }
        ]
    }
}

# 重要常數
STOCK_CODES = {
    "台積電": "2330",
    "大盤": "Y9999",
    "加權指數": "Y9999"
}

CURRENT_DATE = "2025-12-05"

def get_tools_description() -> str:
    """
    生成工具列表的文字描述，供 prompt 使用。
    """
    desc = "**可用工具列表**：\n"
    
    for category_key, category_data in AVAILABLE_TOOLS.items():
        desc += f"\n{category_data['category']}（{category_data['description']}）：\n"
        for tool in category_data['tools']:
            desc += f"  - `{tool['name']}`: {tool['description']}\n"
            desc += f"    參數: {tool['params']}\n"
    
    return desc

def get_tools_examples() -> str:
    """
    生成工具調用範例，供 prompt 使用。
    """
    examples = "**工具調用範例**：\n"
    
    for category_key, category_data in AVAILABLE_TOOLS.items():
        for tool in category_data['tools'][:2]:  # 只顯示前 2 個範例
            examples += f"  {tool['example']}\n"
    
    return examples

def get_recommended_tools_for_topic(topic: str) -> list:
    """
    根據辯題推薦工具。
    """
    topic_lower = topic.lower()
    
    # 台股相關
    if any(keyword in topic for keyword in ["台積電", "股價", "大盤", "台股", "2330"]):
        return ["tej.stock_price", "tej.company_info", "tej.monthly_revenue", "tej.institutional_holdings"]
    
    # 財務相關
    if any(keyword in topic for keyword in ["營收", "獲利", "EPS", "財報"]):
        return ["tej.financial_summary", "tej.monthly_revenue"]
    
    # 預設
    return ["searxng.search"]
