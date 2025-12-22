import sys
import os
sys.path.append(os.getcwd())

from adapters.chinatimes_suite import ChinaTimesStockFundamentalAdapter

def test_chinatimes_fundamental():
    adapter = ChinaTimesStockFundamentalAdapter()
    
    print("Testing with valid code...")
    try:
        result = adapter.invoke(code="2330")
        if result.data:
            print(f"Success! Data keys: {list(result.data.keys())}")
        else:
            print(f"Warning: No data returned but no error. Result: {result.raw}")
    except Exception as e:
        print(f"Failed with valid code: {e}")

    print("\nTesting with missing code...")
    try:
        adapter.invoke()
        print("Error: Should have raised ValueError")
    except ValueError as e:
        print(f"Caught expected ValueError: {e}")
    except Exception as e:
        print(f"Caught unexpected Exception: {type(e)}: {e}")

if __name__ == "__main__":
    test_chinatimes_fundamental()
