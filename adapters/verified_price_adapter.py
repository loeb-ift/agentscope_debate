from typing import Dict, Any, Optional
from .tool_adapter import ToolAdapter
from .base import ToolResult
from worker.utils.price_proof_coordinator import PriceProofCoordinator
import datetime

class VerifiedPriceAdapter(ToolAdapter):
    """
    Verified Price Adapter
    獲取經多源驗證的股價（TEJ/TWSE/Yahoo）。
    """
    name = "financial.get_verified_price"
    version = "v1"
    description = """[Tier 1] 獲取經多源驗證的股價（TEJ/TWSE/Yahoo）。官方/正式數據階層。
    自動處理非交易日（回退至最近交易日），並提供價格可信度證明。
    若 TEJ 資料缺失，會自動嘗試官方 (TWSE) 與外部 (Yahoo) 數據。
    輸入可以是代碼 (2480) 或 (2480.TW)。"""
    
    def __init__(self):
        self.coordinator = PriceProofCoordinator()
    
    @property
    def auth_config(self) -> Dict:
        return {} # Internal or relies on TEJ env var
        
    @property
    def rate_limit_config(self) -> Dict:
        return {"tps": 5, "burst": 10}
        
    @property
    def cache_ttl(self) -> int:
        return 3600 # 1 hour
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string", 
                    "description": "股票代碼 (e.g. 2330, 2330.TW)"
                },
                "date": {
                    "type": "string",
                    "description": "查詢日期 (YYYY-MM-DD)。若遇非交易日自動回退。"
                }
            },
            "required": ["symbol", "date"]
        }
        
    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }
        
    def invoke(self, **kwargs) -> Dict[str, Any]:
        params = kwargs
        symbol = params.get("symbol")
        date_str = params.get("date")
        
        if not symbol:
            raise ValueError("symbol is required")
        if not date_str:
            raise ValueError("date is required")
        
        # Use Coordinator
        # Note: Coordinator handles async, but invoke needs to be sync or async?
        # ToolAdapter usually expects sync invoke in our current architecture (run_in_executor wrapper)
        # PriceProofCoordinator.get_verified_price is sync wrapper.
        
        result = self.coordinator.get_verified_price(symbol, date_str)
        
        return {
            "data": result,
            "_meta": {
                "verified": result.get("verified", False),
                "source": result.get("source", "Unknown")
            }
        }