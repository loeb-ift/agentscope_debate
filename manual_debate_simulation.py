import asyncio
import os
import sys
import yaml

# Ensure app root is in path
sys.path.insert(0, os.getcwd())

from worker.chairman import Chairman
from agentscope.agent import AgentBase
from worker.debate_cycle import DebateCycle
from api.database import SessionLocal
from api.init_data import initialize_all

# Load prompts
def load_prompt(agent_name):
    try:
        with open("prompts/agents/team_agents.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            for item in data:
                if item['name'] == agent_name:
                    return item['system_prompt']
    except Exception as e:
        print(f"Error loading prompt for {agent_name}: {e}")
    return "You are a debater."

async def main():
    print("=== 🚀 手動辯論模擬開始 ===")
    
    # 0. Initialize DB (to ensure prompts/tools are loaded)
    db = SessionLocal()
    initialize_all(db)
    db.close()
    
    topic = "動力-KY(6591)2025年11月合併營收達1.26億元，年成長47.28%"
    print(f"📌 辯題：{topic}")
    
    # 1. Setup Chairman
    # User said: "量化分析師是主席". So we create a Chairman with that name.
    chairman = Chairman(name="量化分析師")
    print(f"👤 主席：{chairman.name}")
    
    # 2. Setup Teams
    # Team A (Pro): Growth Team
    agent_a1 = AgentBase()
    agent_a1.name = "Growth_Strategist"
    agent_a1.system_prompt = load_prompt("Growth_Strategist")
    
    agent_a2 = AgentBase()
    agent_a2.name = "Innovation_Believer"
    agent_a2.system_prompt = load_prompt("Innovation_Believer")
    
    team_a = {
        "name": "Growth Team",
        "side": "pro",
        "agents": [agent_a1, agent_a2]
    }
    
    # Team B (Con): Technical Team
    agent_b1 = AgentBase()
    agent_b1.name = "Technical_Analyst"
    agent_b1.system_prompt = load_prompt("Technical_Analyst")
    
    agent_b2 = AgentBase()
    agent_b2.name = "Market_Trader"
    agent_b2.system_prompt = load_prompt("Market_Trader")
    
    team_b = {
        "name": "Technical Team",
        "side": "con",
        "agents": [agent_b1, agent_b2]
    }
    
    # Team C (Neutral): Macro Team
    # Note: Neutral side triggers verification logic in DebateCycle
    agent_c1 = AgentBase()
    agent_c1.name = "Macro_Economist"
    agent_c1.system_prompt = load_prompt("Macro_Economist")
    
    agent_c2 = AgentBase()
    agent_c2.name = "Policy_Analyst"
    agent_c2.system_prompt = load_prompt("Policy_Analyst")
    
    team_c = {
        "name": "Macro Team",
        "side": "neutral", 
        "agents": [agent_c1, agent_c2]
    }
    
    teams = [team_a, team_b, team_c]
    
    # 3. Initialize Cycle
    cycle = DebateCycle(
        debate_id="manual_test_001",
        topic=topic,
        chairman=chairman,
        teams=teams,
        rounds=3
    )
    
    # 4. Start Debate (Step by Step Simulation via start_async)
    print("\n🎬 辯論開始！")
    try:
        result = await cycle.start_async()
        
        print("\n=== 🏆 辯論結束 ===")
        print("Final Conclusion:")
        print(result["final_conclusion"])
        print("\nJury Report:")
        print(result["jury_report"])
        
    except Exception as e:
        print(f"\n❌ 辯論發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())