import pytest
import asyncio
from datetime import datetime, timedelta
from api.tool_registry import tool_registry
from mars.types.errors import ToolRecoverableError
from adapters.tej_adapter import TEJStockPrice

# Mocking datetime for test stability is hard here without patching system time, 
# so we just use dynamic future dates.

def test_future_date_guard():
    """Test if future dates are blocked by tool_registry."""
    
    # 1. Create a future date
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    params = {
        "coid": "2330",
        "start_date": current_date,
        "end_date": future_date
    }
    
    # TEJStockPrice is registered as 'tej.stock_price'
    tool_data = tool_registry.get_tool_data("tej.stock_price")
    
    # We call the internal guard method directly to test logic
    # (Since invoking tool requires actual API key and network)
    print(f"Testing Future Date Guard with end_date={future_date}...")
    
    try:
        tool_registry._apply_tej_param_guard(tool_data, params)
        assert False, "Should have raised ToolRecoverableError"
    except ToolRecoverableError as e:
        print(f"✅ Caught expected error: {e}")
        assert "日期錯誤" in str(e)
        assert "超過了今日" in str(e)

def test_date_span_guard():
    """Test if date span > 366 days is blocked."""
    
    start_date = "2023-01-01"
    end_date = "2024-02-01" # > 366 days
    
    params = {
        "coid": "2330",
        "start_date": start_date,
        "end_date": end_date
    }
    
    tool_data = tool_registry.get_tool_data("tej.stock_price")
    
    print(f"Testing Date Span Guard with span > 366 days...")
    
    # Note: The original code appended warning 'warn:date_span_too_large' 
    # but _normalize_tej_result raises the exception.
    # Wait, my previous read showed `_normalize_tej_result` raises it.
    # But `_apply_tej_param_guard` returns warnings.
    # So `_apply_tej_param_guard` itself does NOT raise for date span, only for future date (my new change).
    
    # Let's verify `_apply_tej_param_guard` behavior for date span
    p, warnings = tool_registry._apply_tej_param_guard(tool_data, params)
    print(f"Warnings: {warnings}")
    assert "warn:date_span_too_large" in warnings

if __name__ == "__main__":
    try:
        test_future_date_guard()
        test_date_span_guard()
        print("\n🎉 All Guardrail Tests Passed!")
    except Exception as e:
        print(f"\n❌ Tests Failed: {e}")
        exit(1)