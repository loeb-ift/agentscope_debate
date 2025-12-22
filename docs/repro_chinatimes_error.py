
import logging
import sys
from adapters.chinatimes_suite import ChinaTimesStockFundamentalAdapter, ChinaTimesSearchAdapter

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_fundamental_error():
    adapter = ChinaTimesStockFundamentalAdapter()
    print("\n--- Testing chinatimes.stock_fundamental with 'symbol' alias ---")
    try:
        # LLM often sends symbol instead of code
        params = {"symbol": "2330"}
        adapter.invoke(**params)
        print("✅ Success: 'symbol' was correctly mapped to 'code'")
    except Exception as e:
        print(f"❌ Failed: {e}")

    print("\n--- Testing chinatimes.stock_fundamental with nested 'params' ---")
    try:
        # Some frameworks nest parameters
        params = {"params": {"code": "2330"}}
        adapter.invoke(**params)
        print("✅ Success: Nested 'params' were correctly unpacked")
    except Exception as e:
        print(f"❌ Failed: {e}")

def test_search_error():
    adapter = ChinaTimesSearchAdapter()
    print("\n--- Testing news.search_chinatimes with 'q' alias ---")
    try:
        params = {"q": "台積電"}
        adapter.invoke(**params)
        print("✅ Success: 'q' was correctly mapped to 'keyword'")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_fundamental_error()
    test_search_error()
