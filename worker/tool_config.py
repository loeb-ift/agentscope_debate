"""
統一的工具配置，供主席和 Agent 使用。
確保所有代理對可用工具有一致的認知。
"""

from api.tool_registry import tool_registry
import json

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
    從 ToolRegistry 動態獲取，確保包含詳細的欄位說明。
    """
    desc = "**可用工具列表**：\n"
    
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
            desc += f"- **{name}** (v{data['version']})\n"
            # 使用 Adapter 中定義的詳細描述 (包含欄位說明)
            desc += f"  描述: {data['description']}\n"
            desc += f"  Schema: {json.dumps(data['schema'], ensure_ascii=False)}\n"
    
    return desc

def get_tools_examples() -> str:
    """
    生成工具調用範例，供 prompt 使用。
    """
    # 這裡為了簡化，手動定義一些核心範例，或者也可以讓 ToolAdapter 提供 example
    examples = "**核心工具調用範例**：\n"
    examples += '1. 搜尋: {"tool": "searxng.search", "params": {"q": "台積電 2024 Q4 營收"}}\n'
    examples += '2. 股價: {"tool": "tej.stock_price", "params": {"coid": "2330", "start_date": "2024-01-01"}}\n'
    examples += '3. 財報: {"tool": "tej.financial_summary", "params": {"coid": "2330"}}\n'
    
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
