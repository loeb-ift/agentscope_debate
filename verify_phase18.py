import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from worker.debate_cycle import DebateCycle
from worker.chairman import Chairman
from agentscope.agent import AgentBase
from mars.types.errors import ToolRecoverableError

# Mock Redis
patcher = patch("worker.debate_cycle.get_redis_client")
MockRedis = patcher.start()
mock_redis = MagicMock()
MockRedis.return_value = mock_redis

# Mock Hippocampus (uses Redis too)
patcher_mem = patch("worker.debate_cycle.HippocampalMemory")
MockHippocampus = patcher_mem.start()
# Make instance async methods awaitable
MockHippocampus.return_value.retrieve_working_memory = AsyncMock(return_value=None)
MockHippocampus.return_value.store = AsyncMock()

# Mock LTM
patcher_tool_mem = patch("worker.debate_cycle.ReMeToolLongTermMemory")
MockToolMem = patcher_tool_mem.start()
MockToolMem.return_value.record_async = AsyncMock()
MockToolMem.return_value.retrieve_async = AsyncMock(return_value="")
MockToolMem.return_value.flush = AsyncMock()

async def test_database_handshake():
    print("\n--- Testing Database Handshake ---")
    
    # Mock Chairman and Agents
    chairman = MagicMock(spec=Chairman)
    agent = MagicMock(spec=AgentBase)
    agent.name = "TestAgent"
    teams = [{"name": "TestTeam", "side": "pro", "agents": [agent]}]
    
    cycle = DebateCycle("test_db_handshake", "Test Topic", chairman, teams, 1)
    
    # Mock tool invocation for handshake
    with patch("worker.tool_invoker.call_tool") as mock_call:
        # Simulate TEJ returning data up to 2024-12-01
        mock_call.return_value = {
            "data": [{"mdate": "2024-12-01T00:00:00"}, {"mdate": "2024-11-01T00:00:00"}]
        }
        
        await cycle._check_db_date_async()
        
        if cycle.latest_db_date == "2024-12-01":
            print("✅ Database Handshake Success: Latest date detected as 2024-12-01")
        else:
            print(f"❌ Database Handshake Failed: Got {cycle.latest_db_date}")

async def test_data_honesty_warning():
    print("\n--- Testing Data Honesty Warning (Empty Result) ---")
    
    chairman = MagicMock(spec=Chairman)
    agent = MagicMock(spec=AgentBase)
    agent.name = "TestAgent"
    teams = [{"name": "TestTeam", "side": "pro", "agents": [agent]}]
    
    cycle = DebateCycle("test_data_honesty", "Test Topic", chairman, teams, 1)
    cycle.agent_tools_map = {"TestAgent": ["tej.stock_price"]}
    
    # Mock LLM to return a tool call first, then text
    # 1. Call tool
    # 2. Receive result (mocked empty)
    # 3. LLM receives prompt with warning?
    
    # Since we can't easily inspect the internal `current_prompt` local variable of `_agent_turn_async` 
    # without deeper mocking, we will mock `call_llm_async` and check the `prompt` passed to it.
    
    with patch("worker.debate_cycle.call_llm_async", new_callable=AsyncMock) as mock_llm:
        with patch("worker.tool_invoker.call_tool") as mock_tool:
            # Step 1: Agent calls tool
            mock_llm.side_effect = [
                json.dumps({"tool": "tej.stock_price", "params": {"coid": "2330"}}), # First LLM response
                "I conclude." # Second LLM response (after tool)
            ]
            
            # Step 2: Tool returns EMPTY
            mock_tool.return_value = {"data": []} # Empty data
            
            await cycle._agent_turn_async(agent, "pro", 1)
            
            # Check the calls to LLM
            # The 2nd call to LLM should contain the warning
            call_args_list = mock_llm.call_args_list
            if len(call_args_list) >= 2:
                second_call_prompt = call_args_list[1][0][0] # args[0] is prompt
                if "⚠️ **系統警告 (Data Honesty)**" in second_call_prompt and "空數據" in second_call_prompt:
                    print("✅ Data Honesty Warning Success: Warning injected into prompt.")
                else:
                    print(f"❌ Data Honesty Warning Failed: Warning not found in prompt.\nPrompt snippet: {second_call_prompt[:200]}...")
            else:
                print("❌ Data Honesty Warning Failed: LLM not called enough times.")

async def test_loop_detection():
    print("\n--- Testing Loop Detection ---")
    
    chairman = MagicMock(spec=Chairman)
    agent = MagicMock(spec=AgentBase)
    agent.name = "LoopyAgent"
    teams = [{"name": "TestTeam", "side": "pro", "agents": [agent]}]
    
    cycle = DebateCycle("test_loop", "Test Topic", chairman, teams, 1)
    cycle.agent_tools_map = {"LoopyAgent": ["tej.stock_price"]}
    
    with patch("worker.debate_cycle.call_llm_async", new_callable=AsyncMock) as mock_llm:
        # Agent tries to call SAME tool SAME params twice
        tool_call_json = json.dumps({"tool": "tej.stock_price", "params": {"a": 1}})
        
        mock_llm.side_effect = [
            tool_call_json, # Call 1
            tool_call_json, # Call 2 (Should be blocked)
            "Okay I stop."
        ]
        
        # Mock tool execution (irrelevant as loop check is before)
        with patch("worker.tool_invoker.call_tool") as mock_tool:
             mock_tool.return_value = {"data": ["some data"]}
             
             await cycle._agent_turn_async(agent, "pro", 1)
             
             # Check if we logged the loop
             # We can check _loop_sentinel or logs
             # Or check if prompt contained "系統提示：你在本回合已經執行過這個工具"
             
             call_args_list = mock_llm.call_args_list
             # Call 1: Initial
             # Call 2: Result of Tool 1
             # Call 3: Warning about Loop (since LLM tried Call 2 again)
             
             if len(call_args_list) >= 3:
                 third_call_prompt = call_args_list[2][0][0]
                 if "系統提示：你在本回合已經執行過這個工具" in third_call_prompt:
                     print("✅ Loop Detection Success: Agent blocked and warned.")
                 else:
                     print(f"❌ Loop Detection Failed: Warning not found.\nPrompt: {third_call_prompt[:200]}...")
             else:
                 print("❌ Loop Detection Failed: Not enough calls.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_database_handshake())
    loop.run_until_complete(test_data_honesty_warning())
    loop.run_until_complete(test_loop_detection())