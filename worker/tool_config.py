"""
統一的工具配置，供主席和 Agent 使用。
確保所有代理對可用工具有一致的認知。
"""

import json
from datetime import datetime
import os
from worker.tool_manager import tool_manager

# 重要常數
STOCK_CODES = {
    "台積電": "2330",
    "大盤": "Y9999",
    "加權指數": "Y9999"
}

# Dynamic Current Date (Format: YYYY-MM-DD)
# Allow override via SIMULATION_DATE for backtesting or when DB is lagging
CURRENT_DATE = os.getenv("SIMULATION_DATE", datetime.now().strftime("%Y-%m-%d"))

# Deprecated: Logic moved to worker.tool_manager
# Kept for backward compatibility if imported elsewhere
def get_tool_ttl_config() -> dict:
    return {}

def resolve_tool_policy(tool_name: str) -> str:
    return tool_manager.get_tool_config(tool_name).lifecycle

def get_tools_description() -> str:
    """
    生成工具列表的文字描述，供 prompt 使用。
    從 ToolRegistry 動態獲取，確保包含詳細的欄位說明。
    """
    # Use lazy import to avoid circular dependency with api.tool_registry
    from api.tool_registry import tool_registry
    
    desc = "**可用工具列表與使用規範**：\n"
    desc += "> [!IMPORTANT]\n"
    desc += "> **瀏覽工具治理規範**：\n"
    desc += "> 1. **搜尋先行**：你只能申請瀏覽在 `searxng.search` 或其他搜尋工具結果中出現過的 URL。\n"
    desc += "> 2. **一搜一付**：每次成功調用搜尋工具，系統將發放 **1 點瀏覽配額**。調用 `browser.browse` 會消耗 1 點配額。\n"
    desc += "> 3. **策略選擇**：搜尋結果中可能有多個連結，但你只有一次機會。請在思考過程中挑選「最值得瀏覽」的網址進行申請。\n"
    desc += "> 4. **主席核准**：所有瀏覽請求仍須經主席根據邊際效益進行最終審核。\n\n"
    
    # 按群組分類
    tools = tool_registry.list()
    grouped_tools = {}
    
    for name, data in tools.items():
        group = data.get('group', 'basic')
        if group not in grouped_tools:
            grouped_tools[group] = []
        grouped_tools[group].append((name, data))
    
    for group, items in grouped_tools.items():
        desc += f"\n### {group.upper()} 工具組：\n"
        for name, data in items:
            # Ensure schema is loaded for description
            schema = data.get('schema')
            if schema is None:
                try:
                    # Force load to get schema
                    full_data = tool_registry.get_tool_data(name)
                    schema = full_data.get('schema')
                    # Update local description if needed
                    data['description'] = full_data.get('description', data['description'])
                except Exception:
                    pass
            
            desc += f"- **{name}** (v{data['version']})\n"
            # 使用 Adapter 中定義的詳細描述 (包含欄位說明)
            desc += f"  描述: {data['description']}\n"
            desc += f"  Schema: {json.dumps(schema, ensure_ascii=False)}\n"
    
    return desc

from api.config import Config

def _is_tool_registered(name: str) -> bool:
    try:
        # Use lazy import to avoid circular dependency
        from api.tool_registry import tool_registry
        return name in tool_registry.list()
    except Exception:
        return False

def get_tools_examples() -> str:
    """
    生成工具調用範例，供 prompt 使用。
    """
    # 這裡為了簡化，手動定義一些核心範例，或者也可以讓 ToolAdapter 提供 example
    examples = "**核心工具調用範例**：\n"
    examples += '1. 查找公司代號: {"tool": "internal.search_company", "params": {"keyword": "台積電"}}\n'
    examples += '2. 搜尋新聞: {"tool": "searxng.search", "params": {"q": "台積電 2024 Q4 營收"}}\n'
    examples += '3. 查詢最新股價: {"tool": "chinatimes.stock_rt", "params": {"symbol": "2330"}}\n'
    examples += '4. 查詢歷史報表: {"tool": "chinatimes.stock_kline", "params": {"symbol": "2330", "period": "day"}}\n'
    examples += '5. 獲取公信力股價: {"tool": "financial.get_verified_price", "params": {"symbol": "2330"}}\n'
    # 僅在 TEJ 工具啟用且已註冊時，才展示 TEJ 範例
    if Config.ENABLE_TEJ_TOOLS and _is_tool_registered("tej.financial_summary"):
        examples += '6. 查詢標準化財報 (Backup): {"tool": "tej.financial_summary", "params": {"coid": "2330"}}\n'
    
    examples += '5. 查詢全球指數: {"tool": "av.GLOBAL_QUOTE", "params": {"symbol": "DAX"}}\n'
    examples += '6. 查詢美國 CPI: {"tool": "av.CPI", "params": {"interval": "monthly"}}\n'
    examples += '7. 獲取全球數據(Stooq): {"tool": "financial.pdr_reader", "params": {"symbols": ["^SPX"]}}\n'
    
    return examples

def get_recommended_tools_for_topic(topic: str) -> list:
    """
    根據辯題推薦工具。
    """
    topic_lower = topic.lower()
    
    # 推薦工具列表 (全局可用核心工具)
    tools = [
        "searxng.search", 
        "browser.browse", 
        "internal.search_company", 
        "internal.get_company_details"
    ]
    
    # 台股相關
    if any(keyword in topic for keyword in ["台積電", "股價", "大盤", "台股", "2330", "上市", "上櫃"]):
        tools.extend([
            "chinatimes.stock_rt", "chinatimes.stock_kline", "financial.get_verified_price", "twse.stock_day",
        ])
        if Config.ENABLE_TEJ_TOOLS and _is_tool_registered("tej.stock_price"):
            tools.append("tej.stock_price")
        if Config.ENABLE_TEJ_TOOLS and _is_tool_registered("tej.company_info"):
            tools.append("tej.company_info")
    
    # 財務相關
    if any(keyword in topic for keyword in ["營收", "獲利", "EPS", "財報", "月增", "年增"]):
        tools.extend([
            "chinatimes.balance_sheet", "chinatimes.income_statement", "chinatimes.cash_flow", 
            "chinatimes.financial_ratios"
        ])
        if Config.ENABLE_TEJ_TOOLS and _is_tool_registered("tej.financial_summary"):
            tools.append("tej.financial_summary")
    
    # [Macro] 總經與全球市場相關
    if any(keyword in topic_lower for keyword in ["通膨", "利率", "cpi", "fed", "ecb", "利率", "升息", "降息", "非農"]):
        tools.extend([
            "av.CPI", "av.FEDERAL_FUNDS_RATE", "av.TREASURY_YIELD", "av.INFLATION", 
            "av.GLOBAL_QUOTE", "financial.pdr_reader"
        ])

    # [Global] 全球股市相關
    if any(keyword in topic_lower for keyword in ["美股", "歐股", "日股", "道瓊", "標普", "納斯達克", "nasdaq", "dax"]):
        tools.extend(["av.GLOBAL_QUOTE", "financial.pdr_reader", "financial.technical_analysis"])

    # 去重並返回
    return list(dict.fromkeys(tools))
