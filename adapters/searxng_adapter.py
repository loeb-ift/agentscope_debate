from .tool_adapter import ToolAdapter
from typing import Dict, Any
import requests
import json
import hashlib
import os
import time
import random
from api.redis_client import get_redis_client

# 定義可供輪轉的引擎池
# 將 duckduckgo 與 bing 往前排，因為它們對機器人調用相對寬容
ENGINES_POOL = ["duckduckgo", "bing", "google", "brave", "qwant"]

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
        return "[Tier 3] 使用 SearXNG 進行隱私保護的綜合搜尋（支援多搜尋引擎聚合）。數據來自多方媒體與網站，調用時必須在報告中列出具體媒體名稱與原始連結。"

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
                    "default": 5,
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
        limit = kwargs.get("limit", 5)
        engines = kwargs.get("engines")

        params = {"q": q, "categories": category, "format": "json"}
        
        # 實施引擎輪流詢問 (Round-robin)
        if not engines:
            try:
                redis = get_redis_client()
                # 取得並增加全局索引
                engine_idx = redis.incr("searxng:engine_rotation_index")
                selected_engine = ENGINES_POOL[engine_idx % len(ENGINES_POOL)]
                params["engines"] = selected_engine
                print(f"[SearXNG Rotation] Round-robin selected engine: {selected_engine} (Index: {engine_idx})")
            except Exception as re:
                print(f"⚠️ Redis rotation failed, using SearXNG default: {re}")
                # Fallback to a random choice to still achieve some balancing
                params["engines"] = random.choice(ENGINES_POOL)
        else:
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
                
                # Handle SearXNG specific errors that might come with 200 OK or 4xx
                if response.status_code == 429 or "Too many request" in response.text:
                    raise requests.exceptions.RequestException(f"SearXNG Rate Limit: {response.text}")
                
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

            except Exception as e: # Catch generic Exception to handle 429 logic raised above
                last_exception = e
                print(f"⚠️ SearXNG Error: {str(e)[:200]}")
                
                # Retry Logic
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 1.5
                    print(f"🔄 Retrying search in {wait_time:.1f}s... (Attempt {attempt+1}/{max_retries})")
                    
                    # Strategy: Switch Engines on failure
                    # If current engine failed, try the next one in the pool for retry
                    current_engine = params.get("engines")
                    if current_engine in ENGINES_POOL:
                        curr_idx = ENGINES_POOL.index(current_engine)
                        next_engine = ENGINES_POOL[(curr_idx + 1) % len(ENGINES_POOL)]
                        print(f"👉 {current_engine} failed, switching to {next_engine} for retry.")
                        params["engines"] = next_engine
                    else:
                        print("👉 No specific engine bound, falling back to 'duckduckgo' for retry.")
                        params["engines"] = "duckduckgo"
                        
                    time.sleep(wait_time)
                    continue
                
                # Final Failure: Try Google CSE Fallback
                cse_key = os.getenv("GOOGLE_SEARCH_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
                if cse_key:
                    print("🚨 SearXNG completely failed. Fallback to Google CSE (Paid API)...")
                    try:
                        # Lazy import to avoid circular dep if any
                        # Make sure adapter exists or use requests directly if simple
                        try:
                            from adapters.google_cse_adapter import GoogleCSEAdapter
                            cse = GoogleCSEAdapter()
                            return cse.invoke(q=q, limit=limit)
                        except ImportError:
                            # Direct fallback implementation if adapter missing
                            cx = os.getenv("GOOGLE_CSE_ID")
                            if cx:
                                url = "https://www.googleapis.com/customsearch/v1"
                                res = requests.get(url, params={"key": cse_key, "cx": cx, "q": q})
                                res.raise_for_status()
                                items = res.json().get("items", [])
                                norm = [{"title": i.get("title"), "url": i.get("link"), "snippet": i.get("snippet"), "source": "google_cse"} for i in items[:limit]]
                                return {"data": norm, "cost": 0.01, "citations": []}
                    except Exception as cse_e:
                        print(f"❌ Google CSE Fallback failed: {cse_e}")
                            
                # Raise if all fallbacks failed
                # Return empty result instead of crashing the worker?
                print(f"❌ All search attempts failed. Returning empty result to prevent worker crash.")
                return {"data": [], "error": str(e), "cost": 0}
