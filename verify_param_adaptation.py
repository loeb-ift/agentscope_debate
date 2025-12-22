
import os
import sys
from typing import Any, Dict

# 模擬 OpenAPIToolAdapter 的環境
class MockAdapter:
    def __init__(self, expected_params: list):
        self._expected_params = expected_params
        self.provider = "tej"

    @property
    def schema(self):
        return {"properties": {p: {} for p in self._expected_params}}

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        # 實作我們剛才加入 dynamic_tool_loader.py 的邏輯
        params = kwargs.copy()
        warnings = []
        
        ALIAS_MAP = {
            "symbol": ["ticker", "stock_id", "coid"],
            "ticker": ["symbol", "stock_id", "coid"],
            "coid": ["symbol", "ticker", "stock_id", "id"],
            "company_id": ["coid", "ticker", "symbol", "id"]
        }
        
        expected_params = list(self.schema.get("properties", {}).keys())
        
        for target, aliases in ALIAS_MAP.items():
            if target in expected_params and target not in params:
                for alias in aliases:
                    if alias in params:
                        params[target] = params[alias]
                        warnings.append(f"parameter_adapted: {alias} -> {target}")
                        break
        return {"final_params": params, "warnings": warnings}

def test_alias_adaptation():
    print("Running Alias Adaptation Tests...")
    
    # 測試情境 1: TEJ 工具需要 coid，Agent 給了 symbol
    adapter_tej = MockAdapter(["coid", "mdate.gte"])
    result1 = adapter_tej.invoke(symbol="2330", start_date="2023-01-01")
    print(f"Test 1 (TEJ coid): {result1}")
    assert result1["final_params"]["coid"] == "2330"
    assert "parameter_adapted: symbol -> coid" in result1["warnings"]

    # 測試情境 2: yfinance 工具需要 symbol，Agent 給了 ticker
    adapter_yf = MockAdapter(["symbol", "period"])
    result2 = adapter_yf.invoke(ticker="AAPL", period="1mo")
    print(f"Test 2 (yfinance symbol): {result2}")
    assert result2["final_params"]["symbol"] == "AAPL"
    assert "parameter_adapted: ticker -> symbol" in result2["warnings"]

    # 測試情境 3: 已經有正確參數，不應該觸發適配
    result3 = adapter_tej.invoke(coid="2317")
    print(f"Test 3 (Correct param): {result3}")
    assert result3["final_params"]["coid"] == "2317"
    assert len(result3["warnings"]) == 0

    print("✅ All tests passed!")

if __name__ == "__main__":
    test_alias_adaptation()
