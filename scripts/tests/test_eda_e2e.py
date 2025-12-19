
import asyncio
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock database/redis dependencies if running outside docker fully
# But this script is intended to be run via docker exec

async def test_eda_chinatimes_integration():
    """
    E2E Test: Verify EDA Tool uses ChinaTimes data when available.
    """
    print("=" * 60)
    print("🧪 EDA Tool Integration Test: ChinaTimes Data Source")
    print("=" * 60)

    try:
        from adapters.eda_tool_adapter import EDAToolAdapter
        from api.tool_registry import tool_registry
        
        # Ensure necessary adapters are registered (simulating startup)
        # We need ChinaTimes adapters registered for this test
        try:
            # Manually trigger lazy loading or register if not present
            # In a real running container, these might be already registered by main.py
            # But let's be safe for standalone execution
            from adapters.chinatimes_suite import ChinaTimesStockKlineAdapter
            tool_registry.register(ChinaTimesStockKlineAdapter())
            print("✓ ChinaTimesStockKlineAdapter registered")
        except Exception as e:
            print(f"ℹ️  ChinaTimes adapter registration skipped/failed: {e}")

        adapter = EDAToolAdapter()
        
        # Symbol: 2330 (TSMC) - Should be available in ChinaTimes
        symbol = "2330" 
        debate_id = "test_eda_chinatimes_001"
        lookback_days = 30
        
        print(f"\nrunning invoke for symbol={symbol}...")
        
        # invoke calls _invoke_async internally
        # We want to see if it tries to use ChinaTimes logic (which we haven't implemented yet, 
        # but the feedback says "Now the problem is EDA Tool only uses Yahoo Finance")
        # So this test is to Confirm current behavior first, or verify the fix once applied.
        
        # Current behavior check: It should likely use Yahoo Finance logic if not modified.
        # But if we modify EDAToolAdapter to prefer ChinaTimes, we want to verify that.
        
        result = await adapter._invoke_async(
            symbol=symbol,
            debate_id=debate_id,
            lookback_days=lookback_days,
            include_financials=False # Focus on price data first
        )
        
        print("\n📊 Result Summary:")
        print(f"Success: {result.get('success')}")
        if result.get('error'):
            print(f"Error: {result.get('error')}")
            
        # Check artifacts
        artifacts = result.get('artifacts', {})
        print(f"Report: {artifacts.get('report')}")
        
        # Verification Logic:
        # How do we know it used ChinaTimes?
        # 1. We can check logs (if we could capture them)
        # 2. We can check the data CSV content if possible, but that's hard.
        # 3. Ideally, if Yahoo Finance fails (or we force it to fail) and it still works, then it used ChinaTimes.
        
        print("\n✅ Test Execution Completed")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_eda_chinatimes_integration())
