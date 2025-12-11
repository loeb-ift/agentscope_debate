from adapters.yfinance_adapter import YFinanceAdapter
import json

def test_yfinance():
    adapter = YFinanceAdapter()
    print(f"Testing adapter: {adapter.name}")
    
    symbol = "AAPL"
    
    print(f"\nFetching basic info for {symbol}...")
    try:
        result = adapter.invoke(symbol=symbol, info_type="basic")
        print("Success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Failed: {e}")

    print(f"\nFetching history for {symbol}...")
    try:
        result = adapter.invoke(symbol=symbol, info_type="history")
        print("Success! (showing first 2 records)")
        # 只顯示前兩筆，避免輸出過長
        if "data" in result and isinstance(result["data"], list):
            print(json.dumps(result["data"][:2], indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_yfinance()
