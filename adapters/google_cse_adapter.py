from typing import Dict, Any
import os
import requests
from .tool_adapter import ToolAdapter


class GoogleCSEAdapter(ToolAdapter):
    """
    Google Programmable Search (CSE) 搜尋工具。
    需環境變數：GOOGLE_CSE_API_KEY, GOOGLE_CSE_ID
    端點：https://www.googleapis.com/customsearch/v1
    """

    @property
    def name(self) -> str:
        return "google.cse.search"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Google 可程式化搜尋引擎 (CSE)。提供高品質、即時的網路搜尋結果 (需消耗 API 配額)。"

    @property
    def cache_ttl(self) -> int:
        return 3600

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                "lr": {"type": "string", "description": "語言限制 (例如 'lang_zh-TW' 僅搜尋繁體中文)"},
                "cr": {"type": "string", "description": "國家限制 (例如 'countryTW' 僅搜尋台灣網頁)"},
                "sort": {"type": "string", "description": "排序方式 (例如 'date' 按日期排序)"}
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
        api_key = os.getenv("GOOGLE_CSE_API_KEY")
        cse_id = os.getenv("GOOGLE_CSE_ID")
        if not api_key or not cse_id:
            return {"error": "Missing GOOGLE_CSE_API_KEY or GOOGLE_CSE_ID"}

        q = kwargs.get("q")
        limit = int(kwargs.get("limit", 10))
        lr = kwargs.get("lr")
        cr = kwargs.get("cr")

        params = {
            "key": api_key,
            "cx": cse_id,
            "q": q,
            "num": max(1, min(limit, 10)),  # CSE 每次最多 10
        }
        if lr:
            params["lr"] = lr
        if cr:
            params["cr"] = cr

        try:
            resp = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=8)
            resp.raise_for_status()
            raw = resp.json()
            items = raw.get("items", [])
            data = []
            for it in items[:limit]:
                data.append({
                    "title": it.get("title"),
                    "url": it.get("link"),
                    "snippet": it.get("snippet"),
                    "source": "google cse",
                })
            return {
                "data": data,
                "raw": raw,
                "cost": 1,  # 標示為付費/高級來源
                "citations": []
            }
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Google CSE Error: {e}")
