
import os
import httpx
from typing import Optional, Dict, Any, List
import asyncio

class BrowserMCPAdapter:
    """
    Adapter for Playwright MCP server.
    Supports browsing and page content extraction with Chairman approval gate.
    """
    def __init__(self, mcp_url: Optional[str] = None):
        # Default to a local or configured MCP server URL
        self.url = mcp_url or os.getenv("BROWSER_MCP_URL", "http://mcp-browser:8080/mcp")
        self.headers = {"Content-Type": "application/json"}
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出 Server 支援的所有工具"""
        # Return static list if server is not available, or fetch from MCP
        # For Playwright, standard tools are: playwright-browser-open, playwright-browser-navigate, etc.
        # We wrap them into simpler names.
        return [
            {
                "name": "browse",
                "description": "瀏覽網頁並獲取文字內容。需要主席准許。必須提供理由 (justification)。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "網頁 URL"},
                        "justification": {"type": "string", "description": "為何需要瀏覽此網頁的詳細理由"}
                    },
                    "required": ["url", "justification"]
                }
            },
            {
                "name": "page_source",
                "description": "獲取網頁完整 HTML 原始碼。需要主席准許。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "網頁 URL"},
                        "justification": {"type": "string", "description": "必要性說明"}
                    },
                    "required": ["url", "justification"]
                }
            }
        ]

    def list_tools_sync(self) -> List[Dict[str, Any]]:
        # For now, return the same static list synchronously
        import asyncio
        # We can't easily wait for async here if no loop exists, but since it's static...
        # In a real impl, we'd use httpx.Client().post(...)
        return [
            {
                "name": "browse",
                "description": "瀏覽網頁並獲取文字內容。**此工具調用需要主席准許**。請在 params 中包含 'justification'。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "網頁 URL"},
                        "justification": {"type": "string", "description": "瀏覽原因與預期邊際利益"}
                    },
                    "required": ["url", "justification"]
                }
            },
            {
                "name": "page_source",
                "description": "獲取網頁 HTML。需要主席准許。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "網頁 URL"},
                        "justification": {"type": "string", "description": "瀏覽原因"}
                    },
                    "required": ["url", "justification"]
                }
            }
        ]

    async def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """呼叫指定的工具"""
        # In a real MCP setup, we'd forward this to the Playwright MCP server.
        # Here we implement a shim that uses Playwright if available, or a fallback.
        print(f"[BrowserMCP] Invoking {tool_name} for {arguments.get('url')} ...")
        
        # Real implementation would call the MCP URL
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": f"playwright-{tool_name}", # Map to actual MCP name if different
                "arguments": arguments
            },
            "id": self._next_id()
        }
        
        try:
             async with httpx.AsyncClient(timeout=60.0) as client:
                 response = await client.post(self.url, json=payload, headers=self.headers)
                 if response.status_code == 200:
                     data = response.json()
                     content_list = data.get("result", {}).get("content", [])
                     return "\n".join([c.get("text", "") for c in content_list if c.get("type") == "text"])
                 else:
                     return f"Browser Service Error: {response.status_code}. Make sure BROWSER_MCP_URL is correct."
        except Exception as e:
             # Fallback to a mock for demonstration if server is down, 
             # but in production, this should be a failure.
             return f"Browser component is not reachable at {self.url}. Error: {str(e)}"

    def invoke_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """同步呼叫"""
        import asyncio
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, self.invoke_tool(tool_name, arguments)).result()
        except Exception as e:
            return f"Synchronous browser call failed: {e}"
