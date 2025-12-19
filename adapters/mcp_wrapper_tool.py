
from typing import Dict, Any, List

class DynamicMCPTool:
    """
    動態 MCP 工具封裝器。
    將 MCP Adapter 中的單一工具封裝成系統可識別的 Tool Object。
    """
    def __init__(self, adapter, tool_name: str, tool_description: str, input_schema: Dict[str, Any], group: str = "mcp", requires_approval: bool = False):
        self.adapter = adapter
        self.name = tool_name
        self._description = tool_description
        self.schema = input_schema
        self.group = group
        
        # Agentscope/System 兼容性屬性
        self.auth_config = None
        self.rate_limit_config = {"limit": 5, "period": 60} # 預設保守限制
        self.cache_ttl = 300 # 5分鐘快取
        self.requires_approval = requires_approval 

    def describe(self) -> str:
        return self._description

    def invoke(self, **kwargs) -> Any:
        # 使用 Adapter 的同步調用方法 (因為 ToolRegistry 目前是在 Sync Context 下執行)
        # 如果 Adapter 只有 Async invoke，這裡需要用 asyncio.run (但要注意線程問題)
        # 幸好我們剛為了 Coordinator 實作了 invoke_tool_sync
        if hasattr(self.adapter, "invoke_tool_sync"):
            return self.adapter.invoke_tool_sync(self.name, kwargs)
        else:
             # Fallback (Not recommended inside standard execution loop if async)
             import asyncio
             return asyncio.run(self.adapter.invoke_tool(self.name, kwargs))
