
from api.tool_registry import tool_registry
from typing import Dict, Any
from mars.types.errors import ToolError

def call_tool(tool_name: str, params: Dict[str, Any], version: str = "v1") -> Dict[str, Any]:
    """
    調用指定版本的工具。
    """
    try:
        return tool_registry.invoke_tool(tool_name, params, version)
    except ToolError:
        # [Fix] Allow structured ToolError to propagate to DebateCycle
        raise

    # Let other exceptions propagate to be handled by DebateCycle


