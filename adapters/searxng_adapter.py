from .tool_adapter import ToolAdapter
from typing import Dict, Any
import requests
import json
import hashlib
import os

class SearXNGAdapter(ToolAdapter):
    """
    SearXNG 搜尋工具的轉接器。
    """
    @property
    def name(self) -> str:
        return "searxng.search"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "以關鍵字進行隱私搜尋"

    @property
    def cache_ttl(self) -> int:
        return 3600

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字 (Required)"},
                "query": {"type": "string", "description": "Alias for q"},
                "category": {
                    "type": "string",
                    "enum": ["general", "news", "science"],
                    "default": "general",
                    "description": "搜尋類別"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10,
                    "description": "回傳結果數量"
                },
                "engines": {
                    "type": "string",
                    "description": "指定搜尋引擎 (例如: 'google cse', 'brave api', 'bing api')，留空則使用預設聚合"
                }
            },
            "required": [] # Handled in invoke
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        searxng_host = os.getenv("SEARXNG_HOST", "http://searxng:8080")
        base_url = f"{searxng_host}/search"
        q = kwargs.get("q") or kwargs.get("query")
        
        if not q:
            return {"error": "Missing required parameter: q (or query)"}

        category = kwargs.get("category", "general")
        limit = kwargs.get("limit", 10)
        engines = kwargs.get("engines")

        params = {"q": q, "categories": category, "format": "json"}
        if engines:
            params["engines"] = engines

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            raw_data = response.json()
            
            # 標準化數據
            normalized_data = []
            for item in raw_data.get("results", [])[:limit]:
                normalized_data.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("content"),
                    "source": item.get("engine"),
                })

            return {
                "data": normalized_data,
                "raw": raw_data,
                "cost": 0,
                "citations": []
            }

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Upstream Error: {e}")
