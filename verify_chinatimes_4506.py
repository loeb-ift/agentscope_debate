import sys
import os
import logging
from adapters.chinatimes_suite import ChinaTimesStockKlineAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_4506():
    print("🔍 Checking ChinaTimes Kline for 4506 (崇友)...")
    adapter = ChinaTimesStockKlineAdapter()
    result = adapter.invoke(code="4506")
    
    if result.data and isinstance(result.data, list):
        print(f"✅ Data Points: {len(result.data)}")
        if len(result.data) > 0:
            last = result.data[-1]
            print(f"📉 Latest Data: Date={last.get('date')} Close={last.get('close')}")
            
            # Check price reasonability
            close_price = last.get('close')
            if close_price > 500:
                print(f"⚠️ Warning: Price {close_price} seems unusually high for 4506!")
            else:
                print(f"✅ Price {close_price} seems reasonable.")
                
            # Print last 5
            print("\nLast 5 records:")
            for row in result.data[-5:]:
                print(row)
    else:
        print(f"❌ No data returned. Raw: {result.raw}")

if __name__ == "__main__":
    test_4506()