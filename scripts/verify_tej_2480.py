from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from api.redis_client import get_redis_client # Mock target
from adapters.tej_adapter import TEJStockPrice # Mock target

# Mock Redis
with patch('api.redis_client.get_redis_client') as mock_redis:
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_redis.return_value = mock_client
    
    from api.tool_registry import tool_registry

    def test_date_guard():
        print("\n=== Testing TEJ Date Guard (Registry Level) ===")
        # 1. Create a Very Large Date Range (2 Years)
        base_date = datetime(2024, 12, 31)
        start_date = (base_date - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = base_date.strftime("%Y-%m-%d")
        
        print(f"Range: {start_date} to {end_date} (> 366 days)")
        
        params = {
            "coid": "2480.TW",
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Mock the tool instance inside registry to avoid Auth error
        # We need to find the registered instance
        tool_data = tool_registry.get_tool_data("tej.stock_price")
        real_tool = tool_data["instance"]
        
        # Patch invoke on the instance
        with patch.object(real_tool, 'invoke') as mock_invoke:
            # Return dummy data, registry logic should check params/warnings independently
            mock_invoke.return_value = {"data": []} 
            
            try:
                result = tool_registry.invoke_tool("tej.stock_price", params)
                
                print("[Result]")
                if "error" in result:
                    print(f"❌ Error: {result['error']}") # We expect ToolRecoverableError caught here? No, invoke_tool returns dict on exception?
                    # invoke_tool catches exceptions and returns {"error": ...}
                elif "warnings" in result:
                    print(f"⚠️ Warnings: {result['warnings']}")
                else:
                    print("✅ Success (Unexpected if guard worked)")
                    
            except Exception as e:
                print(f"❌ Exception caught outside: {e}")

if __name__ == "__main__":
    test_date_guard()