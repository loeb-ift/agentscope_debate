import sys
import os

# Allow import from current directory
sys.path.insert(0, os.getcwd())

from adapters.chinatimes_suite import (
    ChinaTimesMarketIndexAdapter,
    ChinaTimesMarketRankingsAdapter,
    ChinaTimesSectorAdapter,
    ChinaTimesStockFundamentalAdapter
)

def test_market_index():
    print("\n--- Testing ChinaTimesMarketIndexAdapter ---")
    adapter = ChinaTimesMarketIndexAdapter()
    result = adapter.invoke()
    print(f"Result citations: {len(result.citations)}")
    if result.citations:
        print(f"Sample snippet: {result.citations[0]['snippet']}")
    else:
        print(f"ERROR: {result.raw}")

def test_market_rankings():
    print("\n--- Testing ChinaTimesMarketRankingsAdapter ---")
    adapter = ChinaTimesMarketRankingsAdapter()
    # Test TSE
    result = adapter.invoke(mkt_type="TSE")
    print(f"TSE Result citations: {len(result.citations)}")
    if result.citations:
         print(f"TSE Snippet: {result.citations[0]['snippet']}")
    
    # Test OTC (optional)
    # result_otc = adapter.invoke(mkt_type="OTC")

def test_sector_info():
    print("\n--- Testing ChinaTimesSectorAdapter ---")
    adapter = ChinaTimesSectorAdapter()
    # Test Sector 12 (Food?) or 37 (suggested in Postman)
    sid = "37" 
    print(f"Testing Sector {sid} (List)...")
    result = adapter.invoke(sector_id=sid, action="list")
    print(f"List Result citations: {len(result.citations)}")
    
    print(f"Testing Sector {sid} (Performance)...")
    result_perf = adapter.invoke(sector_id=sid, action="performance")
    print(f"Perf Result citations: {len(result_perf.citations)}")

def test_stock_fundamental():
    print("\n--- Testing ChinaTimesStockFundamentalAdapter ---")
    adapter = ChinaTimesStockFundamentalAdapter()
    code = "2330"
    print(f"Testing Stock {code}...")
    result = adapter.invoke(code=code)
    print(f"Result citations: {len(result.citations)}")
    if result.citations:
        print(f"Snippet: {result.citations[0]['snippet']}")


if __name__ == "__main__":
    try:
        test_market_index()
        test_market_rankings()
        test_sector_info()
        test_stock_fundamental()
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
