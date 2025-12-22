from .tool_adapter import ToolAdapter
from typing import Dict, Any
# Deprecated: shim to searxng.search with engines='duckduckgo'
from adapters.searxng_adapter import SearXNGAdapter

class DuckDuckGoAdapter(ToolAdapter):
    """
    DuckDuckGo 搜尋工具的轉接器。
    """
    @property
    def name(self) -> str:
        return "duckduckgo.search"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "DuckDuckGo 隱私搜尋引擎 (相容模式)。提供基本的網頁搜尋功能，不追蹤使用者。"

    @property
    def cache_ttl(self) -> int:
        return 3600

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字"},
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                    "description": "回傳結果數量上限"
                }
            },
            "required": ["q"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Deprecated shim: route to searxng.search with engines='duckduckgo'.
        保留 duckduckgo.search 名稱，內部統一走 searxng 以降低維護成本。
        """
        q = kwargs.get("q")
        max_results = kwargs.get("max_results", 5)
        sx = SearXNGAdapter()
        resp = sx.invoke(q=q, limit=max_results, engines='duckduckgo')
        # resp['data'] 已是標準化格式，保持返回結構一致
        return resp
