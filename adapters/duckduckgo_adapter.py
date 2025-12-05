from .tool_adapter import ToolAdapter
from typing import Dict, Any
from duckduckgo_search import DDGS

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
        return "使用 DuckDuckGo 進行網頁搜尋"

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
                    "default": 10,
                    "description": "回傳結果數量"
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
        q = kwargs.get("q")
        max_results = kwargs.get("max_results", 10)

        try:
            with DDGS() as ddgs:
                raw_results = [r for r in ddgs.text(q, max_results=max_results)]
            
            # Normalize the data
            normalized_data = []
            for item in raw_results:
                normalized_data.append({
                    "title": item.get("title"),
                    "url": item.get("href"),
                    "snippet": item.get("body"),
                    "source": "duckduckgo"
                })

            return {
                "data": normalized_data,
                "raw": raw_results,
                "cost": 0,
                "citations": []
            }

        except Exception as e:
            raise RuntimeError(f"DuckDuckGo Error: {e}")
