import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from api.tool_registry import tool_registry

async def test_pdr_tool():
    print("Testing financial.pdr_reader tool...")
    params = {
        "symbol": "2330.TW",
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "source": "stooq"
    }
    
    result = tool_registry.invoke_tool("financial.pdr_reader", params)
    
    if result.get("success"):
        print("✓ PDR tool SUCCESS")
        print(f"Data count: {result.get('count')}")
        if result.get('data'):
            print(f"Sample data: {result.get('data')[0]}")
    else:
        print(f"✗ PDR tool FAILED: {result.get('error')}")

async def test_eda_priority():
    print("\nTesting EDA priority chain (triggering PDR)...")
    # We use a symbol that likely fails in ChinaTimes but works in PDR/Stooq
    # Or just rely on the fact that my previous test showed ChinaTimes failing in this env
    debate_id = "test_pdr_priority"
    params = {
        "symbol": "AAPL",
        "debate_id": debate_id,
        "lookback_days": 30,
        "include_financials": False,
        "include_technical": False
    }
    
    result = tool_registry.invoke_tool("chairman.eda_analysis", params)
    
    if result.get("success"):
        print("✓ EDA analysis tool SUCCESS")
        # Check which file was created
        data_dir = Path("data/staging") / debate_id
        if (data_dir / "AAPL_pdr.csv").exists():
            print("✓ Confirmed: PDR source was used")
        elif (data_dir / "AAPL.csv").exists():
            print("! Fallback to Yahoo Finance used instead of PDR")
        else:
            print("? Neither PDR nor Yahoo CSV found")
    else:
        print(f"✗ EDA analysis tool FAILED: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_pdr_tool())
    asyncio.run(test_eda_priority())
