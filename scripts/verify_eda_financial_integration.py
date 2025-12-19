
import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock environment
os.environ["API_KEY"] = "test"
os.environ["API_BASE_URL"] = "http://test"

def mock_call_tool_sync(tool_name, params):
    """Synchronous mock matching adapter's run_in_executor usage"""
    print(f"Mocking sync tool call: {tool_name}")
    if tool_name == "chinatimes.stock_kline":
        return {
            "data": [
                {"date": "2023-01-01", "open": 100, "high": 105, "low": 98, "close": 102, "volume": 1000},
                {"date": "2023-01-02", "open": 102, "high": 108, "low": 100, "close": 106, "volume": 1500},
                {"date": "2023-01-03", "open": 106, "high": 110, "low": 105, "close": 108, "volume": 1200},
            ]
        }
    elif tool_name == "chinatimes.stock_fundamental":
        return {
            "Code": "2330",
            "Name": "TSMC",
            "EPS": 10.5,
            "ROE": 25.6,
            "PERatio": 20.1,
            "DividendYield": 2.5
        }
    elif tool_name == "chinatimes.financial_ratios":
        return {
            "data": {
                "debt_ratio": 35.5,
                "current_ratio": 2.1,
                "gross_margin": 52.3
            }
        }
    elif tool_name == "ods.eda_describe":
        return {
            "success": True,
            "data": {
                "report_path": "/tmp/report.html",
                "plot_paths": ["/tmp/plot1.png"],
                "table_paths": ["/tmp/table.csv"],
                "metadata": {"rows": 3, "cols": 15}
            }
        }
    return {"error": "Unknown tool"}

async def test_eda_integration():
    """Test full EDA integration logic"""
    print("Testing EDA Tool Adapter Integration...")
    
    # Patch where the adapter imports call_tool
    with patch("worker.tool_invoker.call_tool", side_effect=mock_call_tool_sync):
        from adapters.eda_tool_adapter import EDAToolAdapter
        
        adapter = EDAToolAdapter()
        
        # Avoid DB interaction when ingesting artifacts
        adapter._ingest_artifacts = MagicMock(return_value=[
            MagicMock(id="ev_1", artifact_type="report"),
            MagicMock(id="ev_2", artifact_type="plot")
        ])
        
        # Test 1: Full flow with financials
        print("\n--- Test 1: Full Flow (with Financials) ---")
        result = await adapter._invoke_async(
            symbol="2330.TW",
            debate_id="test_debate_001",
            lookback_days=30,
            include_financials=True
        )
        
        print(f"Success: {result['success']}")
        if result['success']:
            print("Summary Preview:")
            print(result['summary'][:200] + "...")
            
            fin_data = result.get('financial_data')
            if fin_data and fin_data['success']:
                print("✅ Financial data included in result")
                print(f"EPS: {fin_data['fundamental'].get('eps')}")
                print(f"Debt Ratio: {fin_data['ratios'].get('debt_ratio')}")
            else:
                print("❌ Financial data missing")
        else:
            print(f"Error: {result.get('error')}")

        # Check if CSV was created and contains financial columns
        csv_path = Path(__file__).parent / "data" / "staging" / "test_debate_001" / "2330.TW_ct.csv"
        if csv_path.exists():
            import pandas as pd
            df = pd.read_csv(csv_path)
            print("\nCSV Columns:")
            print(df.columns.tolist())
            expected_cols = ['eps', 'roe', 'debt_ratio', 'gross_margin']
            missing = [c for c in expected_cols if c not in df.columns]
            if not missing:
                print("✅ All expected financial columns present in CSV")
            else:
                print(f"❌ Missing columns in CSV: {missing}")
        else:
            print("❌ CSV file not found")

if __name__ == "__main__":
    # Create dummy dirs
    (Path(__file__).parent / "data" / "staging" / "test_debate_001").mkdir(parents=True, exist_ok=True)
    
    # Run test
    try:
        asyncio.run(test_eda_integration())
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        shutil.rmtree(Path(__file__).parent / "data", ignore_errors=True)
