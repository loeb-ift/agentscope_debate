import asyncio
import os
import sys
import yaml
import json

# Ensure app root is in path
sys.path.insert(0, os.getcwd())

from worker.chairman import Chairman
from agentscope.agent import AgentBase
from worker.debate_cycle import DebateCycle
from api.database import SessionLocal
from api.init_data import initialize_all
from api.tool_registry import tool_registry

async def main():
    print("=== 🚀 Live Debate Integration Test (Pricing Tools) ===")
    
    # 0. Initialize DB and Tools
    print("Initializing Database & Tools...")
    db = SessionLocal()
    initialize_all(db) # This loads tool registry from config
    db.close()
    
    # Force verify registry has our new tools
    tools = tool_registry.list()
    required = ["twse.stock_day", "yahoo.stock_price", "financial.get_verified_price"]
    missing = [t for t in required if t not in tools]
    if missing:
        print(f"❌ Critical Error: Missing tools in registry: {missing}")
        return
    print("✅ All pricing tools registered successfully.")

    topic = "台積電(2330) 2024年11月股價波動分析"
    print(f"📌 辯題：{topic}")
    
    # 1. Setup Chairman
    chairman = Chairman(name="Chief_Analyst")
    
    # 2. Setup Agents (Minimal: 1 Pro, 1 Neutral)
    # Pro Agent: Should pick TEJ or fallback
    agent_pro = AgentBase()
    agent_pro.name = "Market_Trader"
    agent_pro.system_prompt = "你是專業交易員。請關注市場價格波動。"
    
    team_pro = {
        "name": "Pro Team",
        "side": "pro",
        "agents": [agent_pro]
    }
    
    # Neutral Agent: Should pick Verified Price or TWSE
    agent_neutral = AgentBase()
    agent_neutral.name = "Risk_Manager"
    agent_neutral.system_prompt = "你是風險經理。請負責查證數據真實性。"
    
    team_neutral = {
        "name": "Neutral Team",
        "side": "neutral",
        "agents": [agent_neutral]
    }
    
    teams = [team_pro, team_neutral]
    
    # 3. Initialize Cycle
    cycle = DebateCycle(
        debate_id="test_integration_001",
        topic=topic,
        chairman=chairman,
        teams=teams,
        rounds=1 # Run only 1 round for testing
    )
    
    # 4. Start Debate
    print("\n🎬 模擬辯論開始 (Round 1 only)...")
    try:
        # We manually trigger steps to control flow if needed, but start_async is easier
        # We will capture logs via the stream log file
        
        # Clear previous log if exists
        if os.path.exists(cycle.stream_log_path):
            os.remove(cycle.stream_log_path)
            
        await cycle.start_async()
        
        print("\n=== 🔍 驗證日誌 (Log Verification) ===")
        if os.path.exists(cycle.stream_log_path):
            with open(cycle.stream_log_path, "r", encoding="utf-8") as f:
                logs = f.read()
                
            # Check Pro Agent Tool Selection
            if "Market_Trader" in logs and ("tej.stock_price" in logs or "internal.search_company" in logs):
                print("✅ Pro Agent selected appropriate tools (TEJ/Search).")
            else:
                print("⚠️ Pro Agent tool selection might be suboptimal. Check logs.")
                
            # Check Neutral Agent Tool Selection
            if "Risk_Manager" in logs and ("financial.get_verified_price" in logs or "twse.stock_day" in logs):
                print("✅ Neutral Agent selected Verified/TWSE tools.")
            else:
                print("⚠️ Neutral Agent did NOT select Verified/TWSE tools. Check logs.")
                
            # Check for actual execution
            if "TOOL_RESULT" in logs:
                print("✅ Tools were executed successfully.")
            else:
                print("❌ No tool execution detected in logs.")
                
            # Check for fallback warning (TEJ missing key)
            if "TEJ_API_KEY missing" in logs:
                print("✅ TEJ missing key warning detected (Expected in this env).")
                
            print("\n--- Log Snippet (Last 20 lines) ---")
            print("\n".join(logs.splitlines()[-20:]))
            
        else:
            print("❌ Log file not found!")
        
    except Exception as e:
        print(f"\n❌ 模擬失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())