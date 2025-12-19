import sys
import os
import json

# Add current dir to path to import adapters
sys.path.append(os.getcwd())

from adapters.twse_adapter import TWSEStockDay

def test_twse():
    adapter = TWSEStockDay()
    print(f"Testing {adapter.name}...")
    
    # Test case: TSMC (2330) for a recent month (e.g., 2024-12-01)
    # Note: TWSE API takes date to find the month.
    # We use a date that surely has data (e.g. last month if today is early in month, or current month).
    # Assuming current date is 2025-12-13 (from context), let's query 2024-12-01 to see historical data logic.
    # Wait, 2025-12-13 is the simulated date. The real world date is 2024 (or 2025 in simulation?).
    # The TWSE API is REAL. So I must use a REAL past date.
    # Today is 2024 (in reality). Let's use 2023-12-01 to be safe, or just 2024-01-01.
    
    # Let's try to get 2024-11-01.
    params = {
        "symbol": "2330",
        "date": "20241101" 
    }
    
    try:
        result = adapter.invoke(params)
        print("Success!")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_twse()