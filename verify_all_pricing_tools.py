import sys
import os
import json
sys.path.append(os.getcwd())

from adapters.tej_adapter import TEJStockPrice
from adapters.twse_adapter import TWSEStockDay
from adapters.yahoo_adapter import YahooStockPrice
from adapters.verified_price_adapter import VerifiedPriceAdapter

def test_tool(name, adapter, params):
    print(f"\n--- Testing {name} ---")
    try:
        result = adapter.invoke(params)
        print(f"Status: Success")
        if hasattr(result, 'data'):
            # Print summary to avoid spam
            data = result.data
            if "rows" in data:
                print(f"Rows returned: {len(data['rows'])}")
                if len(data['rows']) > 0:
                    print(f"First row: {data['rows'][0]}")
            elif "price" in data:
                 print(f"Verified Price: {data['price']}")
                 print(f"Source: {data['source']}")
                 print(f"Warnings: {data['warnings']}")
            else:
                 print(f"Data: {str(data)[:200]}...")
        else:
            print(f"Result: {result}")
    except Exception as e:
        print(f"Status: Failed (Expected if no API key)")
        print(f"Error: {e}")

def run_tests():
    symbol_tw = "2330.TW"
    symbol_id = "2330"
    date_str = "2024-11-01"
    
    # 1. Test TEJ (Primary)
    # Expecting Auth Error or Success if key exists
    test_tool("TEJ Stock Price", TEJStockPrice(), 
              {"coid": symbol_id, "start_date": "2024-11-01", "end_date": "2024-11-05"})

    # 2. Test TWSE (Backup 1)
    test_tool("TWSE Stock Day", TWSEStockDay(), 
              {"symbol": symbol_id, "date": "20241101"})

    # 3. Test Yahoo (Backup 2)
    test_tool("Yahoo Stock Price", YahooStockPrice(), 
              {"symbol": symbol_tw, "start_date": "2024-11-01", "end_date": "2024-11-05"})

    # 4. Test Verified Price (Coordinator/Fallback Logic)
    # Should fallback to TWSE/Yahoo if TEJ fails
    test_tool("Verified Price (Fallback Mechanism)", VerifiedPriceAdapter(), 
              {"symbol": symbol_tw, "date": date_str})

if __name__ == "__main__":
    run_tests()