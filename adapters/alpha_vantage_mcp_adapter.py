
import os
import httpx
from typing import Optional, Dict, Any, List

# Alpha Vantage MCP implementation is a stateless HTTP JSON-RPC endpoint (mcp-lambda-server)
# It does not require SSE connection or initialization sequence for basic tool usage.

class AlphaVantageMCPAdapter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is not set")
        
        self.url = f"https://mcp.alphavantage.co/mcp?apikey={self.api_key}"
        self.headers = {"Content-Type": "application/json"}
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出 Server 支援的所有工具"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": self._next_id()
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise RuntimeError(f"MCP Error: {data['error']}")
                
            tools = data.get("result", {}).get("tools", [])
            return tools

    def list_tools_sync(self) -> List[Dict[str, Any]]:
        """列出 Server 支援的所有工具 (同步)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": self._next_id()
        }
        
        with httpx.Client() as client:
            response = client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise RuntimeError(f"MCP Error: {data['error']}")
                
            tools = data.get("result", {}).get("tools", [])
            return tools

    async def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """呼叫指定的工具"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self._next_id()
        }
        
        print(f"[AlphaVantageMCP] Invoking {tool_name} args={arguments} ...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                 raise RuntimeError(f"MCP Tool Execution Error: {data['error']}")
            
            # MCP CallToolResult structure
            # result -> content -> list[dict(type, text)]
            content_list = data.get("result", {}).get("content", [])
            
            texts = []
            for item in content_list:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "resource":
                    texts.append(f"[Resource] {item.get('resource', {}).get('uri')}")
            
            
            return "\n".join(texts)

    def invoke_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """同步呼叫指定的工具 (Blocking)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self._next_id()
        }
        
        print(f"[AlphaVantageMCP] Invoking Sync {tool_name} args={arguments} ...")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                 raise RuntimeError(f"MCP Tool Execution Error: {data['error']}")
            
            content_list = data.get("result", {}).get("content", [])
            
            texts = []
            for item in content_list:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "resource":
                    texts.append(f"[Resource] {item.get('resource', {}).get('uri')}")
            
            return "\n".join(texts)
