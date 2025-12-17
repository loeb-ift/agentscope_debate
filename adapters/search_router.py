
from typing import Dict, Any, Optional
from .tool_adapter import ToolAdapter
from .searxng_adapter import SearXNGAdapter
from .google_cse_adapter import GoogleCSEAdapter
from api.quota_service import quota_service
import os

class SearchRouter(ToolAdapter):
    """
    智慧搜尋路由 (Smart Search Router)
    - 根據角色 (role) 與配額 (quota) 自動選擇搜尋引擎。
    - 支援 `search.paid` (Google CSE) 與 `search.free` (SearXNG)。
    - 自動降級機制：當配額用盡或 API 錯誤時自動切換至免費層。
    """
    
    def __init__(self):
        self.searxng = SearXNGAdapter()
        self.google = GoogleCSEAdapter()
        
        # Role mapping for Tier 1 access (Paid)
        # These roles default to Paid search if quota allows
        self.paid_roles = ["chairman", "reviewer", "guardrail", "manager"]

    @property
    def name(self) -> str:
        return "search.smart"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "智慧搜尋路由：根據角色權限與配額自動選擇最佳搜尋引擎 (Google/SearXNG)。"

    @property
    def cache_ttl(self) -> int:
        return 3600

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字"},
                "limit": {"type": "integer", "default": 10},
                "role": {"type": "string", "description": "調用者角色 (影響路由決策)"},
                "tier": {"type": "string", "enum": ["free", "paid"], "description": "強制指定層級 (可選)"},
                "engines": {"type": "string", "description": "特定引擎 (僅轉發給 SearXNG, 如 'duckduckgo')"}
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
        if not q:
            return {"error": "Missing required parameter: q"}

        role = kwargs.get("role", "unknown").lower()
        tier = kwargs.get("tier")
        engines = kwargs.get("engines")
        
        # 1. Routing Logic
        use_paid = False
        reason = "default_free"

        # Explicit tier request
        if tier == "paid":
            use_paid = True
            reason = "explicit_paid"
        elif tier == "free":
            use_paid = False
            reason = "explicit_free"
        
        # Role-based default
        elif role in self.paid_roles:
            use_paid = True
            reason = f"role_{role}"
            
        # If engines specificed, typically implies specialized free search (e.g. duckduckgo via searxng)
        if engines:
            use_paid = False
            reason = "engine_specified"

        # 2. Check Quota & Degradation
        if use_paid:
            if not quota_service.check_quota():
                use_paid = False
                reason += "_but_quota_exceeded"
                # TODO: Emit warning event?
                print(f"⚠️ SearchRouter: Quota exceeded for {role}. Downgrading to Free tier.")
        
        # 3. Dispatch
        result = {}
        source_adapter = None
        
        if use_paid:
            try:
                # Try Google CSE
                print(f"[SearchRouter] Routing to PAID (Google CSE) | Reason: {reason}")
                result = self.google.invoke(**kwargs)
                
                # Check for execution errors (not empty results, but actual API errors)
                if isinstance(result, dict) and result.get("error"):
                     raise RuntimeError(result.get("error"))
                     
                source_adapter = "google"
                quota_service.increment()
                
            except Exception as e:
                print(f"⚠️ SearchRouter: Paid search failed ({e}). Fallback to Free.")
                use_paid = False # Fallback
                reason += "_fallback_on_error"

        if not use_paid:
            # SearXNG
            print(f"[SearchRouter] Routing to FREE (SearXNG) | Reason: {reason}")
            # Ensure 'engines' is passed correctly if SearXNG supports it
            result = self.searxng.invoke(**kwargs)
            source_adapter = "searxng"

        # 4. Enhance Metadata
        if isinstance(result, dict):
            meta = result.get("_meta", {})
            meta["router_reason"] = reason
            meta["router_source"] = source_adapter
            result["_meta"] = meta
            
            # Tier tagging for Verification Gate
            if use_paid:
                result["_tier"] = "paid" 
                # Mark items as high quality if needed by Verifier
            else:
                result["_tier"] = "free"

        return result
