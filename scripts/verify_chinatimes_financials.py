import requests
from adapters.chinatimes_suite import (
    ChinaTimesBalanceSheetAdapter,
    ChinaTimesIncomeStatementAdapter,
    ChinaTimesCashFlowAdapter,
    ChinaTimesFinancialRatiosAdapter
)

def test_tool(tool_class, code="2330"):
    tool = tool_class()
    print(f"Testing {tool.name} for code {code}...")
    try:
        # 這裡我們模擬呼叫，但這會真的發送請求
        # 由於是內網 IP，如果不通是預期的，我們主要驗證 Adapter 邏輯與 URL 構造
        result = tool.invoke(code=code)
        
        # ToolResult is an object, access attributes directly
        data = result.data
        
        print(f"Result Status: {'Success' if 'error' not in data else 'Failed'}")
        if 'error' in data:
            print(f"Error: {data['error']}")
        else:
            # 簡單印出一些 keys 驗證結構
            if isinstance(data, dict):
                print(f"Data Keys: {list(data.keys())[:5]}")
            elif isinstance(data, list) and data:
                print(f"Data List (first item keys): {list(data[0].keys())[:5]}")
            else:
                print(f"Data: {str(data)[:100]}")
                
    except Exception as e:
        print(f"Exception: {e}")
    print("-" * 30)

if __name__ == "__main__":
    print("Verifying ChinaTimes Financial Tools...\n")
    test_tool(ChinaTimesBalanceSheetAdapter)
    test_tool(ChinaTimesIncomeStatementAdapter)
    test_tool(ChinaTimesCashFlowAdapter)
    test_tool(ChinaTimesFinancialRatiosAdapter)