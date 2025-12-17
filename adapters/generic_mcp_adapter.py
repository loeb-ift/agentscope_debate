
import httpx
from typing import Optional, Dict, Any, List

class GenericMCPAdapter:
    """
    通用 MCP 客戶端轉接器 (Client Adapter)。
    支援連接符合 MCP (Model Context Protocol) 規範的無狀態 HTTP JSON-RPC 伺服器。
    用於整合外部工具集 (如 Alpha Vantage, N8N 等)。
    """
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        # 如果 URL 中沒有包含 apiKey 但有提供，自動附加於 Query String
        # (針對 Alpha Vantage 風格，其他 Server 可能需要 Header)
        # TODO: 這邊需要更彈性的 config。目前為兼容 AV，簡單附加。
        if self.api_key and "apikey=" not in self.base_url:
             separator = "&" if "?" in self.base_url else "?"
             self.url = f"{self.base_url}{separator}apikey={self.api_key}"
        else:
             self.url = self.base_url
             
        self.headers = {"Content-Type": "application/json"}
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出 Server 支援的所有工具 (Async)"""
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
        """列出 Server 支援的所有工具 (Sync)"""
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
        """呼叫指定的工具 (Async)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self._next_id()
        }
        
        # print(f"[MCP] Invoking {tool_name} args={arguments} ...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
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
            
    def invoke_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """呼叫指定的工具 (Sync Blocking)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self._next_id()
        }
        
        # print(f"[MCP] Invoking Sync {tool_name} args={arguments} ...")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.url, json=payload, headers=self.headers)
            # 處理 500 error 但 body 有 error message 的情況 (AV 特性)
            # httpx raise_for_status 會丟錯，我們可能要先讀內容
            # 但標準 MCP 應該回 200 + JSONRPC Error?
            # User reported AV 500 but still valid JSON sometimes?
            # Standard: if status != 200, assume transport error.
            if response.status_code >= 400:
                 # Try parse error body
                 try:
                     err_data = response.json()
                     if "error" in err_data:
                         raise RuntimeError(f"MCP Server Error: {err_data['error']}")
                 except:
                     pass
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
