
import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock environment
os.environ["API_KEY"] = "test"
os.environ["API_BASE_URL"] = "http://test"

# Make mocks awaitable if needed, or regular dicts if not
async def mock_call_tool(tool_name, params):
    """Mock tool invocation"""
    print(f"Mocking tool call: {tool_name} with {params}")
    
    # Simulate IO delay
    await asyncio.sleep(0.1)
    
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
    
    # We need to patch where the code imports it. 
    # Since we can't easily control the import inside the method, we'll patch the module function directly
    # But wait, the code uses `from worker.tool_invoker import call_tool` inside methods.
    # So we need to patch `worker.tool_invoker.call_tool`
    
    with patch("worker.tool_invoker.call_tool", side_effect=mock_call_tool) as mock:
        from adapters.eda_tool_adapter import EDAToolAdapter
        
        adapter = EDAToolAdapter()
        
        # Override _invoke_async to handle the event loop issue in test environment
        # The original code creates a NEW loop which conflicts with running loop in this test
        # We will call _invoke_async directly since we are already in an async function
        
        print("\n--- Test 1: Full Flow (with Financials) ---")
        
        # Note: The adapter uses `loop.run_in_executor(None, call_tool, ...)`
        # This expects call_tool to be synchronous because it's running in an executor!
        # BUT our mock is async. This is the mismatch.
        # Let's fix the mock to be synchronous, because `call_tool` in reality is likely synchronous 
        # (or at least treated as such by run_in_executor in this specific adapter implementation)
        
        # Wait, looking at the code:
        # `result = await loop.run_in_executor(None, call_tool, "chinatimes.stock_kline", ...)`
        # This implies `call_tool` is a blocking synchronous function.
        
        # Let's redefine mock to be synchronous
        def mock_call_tool_sync(tool_name, params):
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

        mock.side_effect = mock_call_tool_sync
        
        # Mock _ingest_artifacts since we don't want real DB interaction
        adapter._ingest_artifacts = MagicMock(return_value=[
            MagicMock(id="ev_1", artifact_type="report"),
            MagicMock(id="ev_2", artifact_type="plot")
        ])
        
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
            
            # Verify financial data in result
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
