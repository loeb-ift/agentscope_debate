
from api.tool_registry import tool_registry
from typing import Dict, Any

def call_tool(tool_name: str, params: Dict[str, Any], version: str = "v1") -> Dict[str, Any]:
    """
    調用指定版本的工具。
    """
    try:
        return tool_registry.invoke_tool(tool_name, params, version)
    except Exception as e:
        # 處理未知錯誤
        return {"error": f"An unexpected error occurred: {e}"}

