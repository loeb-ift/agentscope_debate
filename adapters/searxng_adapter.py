from .tool_adapter import ToolAdapter
from typing import Dict, Any
import requests
import json
import hashlib
import os
import time
import random

# Lazy import to avoid circular dependency if possible, or just import
# from adapters.google_cse_adapter import GoogleCSEAdapter

class SearXNGAdapter(ToolAdapter):
    # 簡單的類別級別 Rate Limiter
    _last_request_time = 0
    _min_interval = 1.0  # 最小間隔 1 秒
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
        return "使用 SearXNG 進行隱私保護的綜合搜尋（支援多搜尋引擎聚合）。適用於一般網路資料查找。"

    @property
    def cache_ttl(self) -> int:
        return 3600

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字"},
                "query": {"type": "string", "description": "q 的別名"},
                "category": {
                    "type": "string",
                    "enum": ["general", "news", "science"],
                    "default": "general",
                    "description": "搜尋類別：一般(general)、新聞(news)、科學(science)"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10,
                    "description": "回傳結果數量限制"
                },
                "engines": {
                    "type": "string",
                    "description": "指定特定引擎 (如 'google', 'bing', 'duckduckgo')，留空則自動聚合最佳來源"
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

        max_retries = 2
        last_exception = None

        for attempt in range(max_retries + 1):
            # Rate Limiting
            now = time.time()
            elapsed = now - SearXNGAdapter._last_request_time
            if elapsed < SearXNGAdapter._min_interval:
                time.sleep(SearXNGAdapter._min_interval - elapsed)
            SearXNGAdapter._last_request_time = time.time()

            try:
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                raw_data = response.json()
                
                # Check for empty results if engines specified (might be blocked)
                # But empty results are valid. The issue is when SearXNG returns error in JSON?
                # Usually HTTP 200 with empty results.
                
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
                last_exception = e
                # Retry Logic
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                    print(f"⚠️ SearXNG Error ({e}). Retrying in {wait_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                    
                    if engines and attempt == max_retries - 1:
                        print("🔄 Retry strategy: Removing specific engines restriction.")
                        params.pop("engines", None)
                        
                    time.sleep(wait_time)
                    continue
                else:
                    # Final Failure: Try Google CSE Fallback
                    # Only if API key is present
                    cse_key = os.getenv("GOOGLE_SEARCH_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
                    if cse_key:
                        print("🚨 SearXNG completely failed. Fallback to Google CSE (Paid API)...")
                        try:
                            # Lazy import to avoid circular dep if any
                            from adapters.google_cse_adapter import GoogleCSEAdapter
                            cse = GoogleCSEAdapter()
                            return cse.invoke(q=q, limit=limit)
                        except Exception as cse_e:
                            print(f"❌ Google CSE Fallback failed too: {cse_e}")
                            
                    raise RuntimeError(f"Upstream Error after retries & fallback: {e}")
