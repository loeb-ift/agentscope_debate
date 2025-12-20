
import asyncio
import sys
import os
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.getcwd())

from api.database import SessionLocal
from api import models
from worker.debate_cycle import DebateCycle
from agentscope.agent import AgentBase

class MockAgent(AgentBase):
    def __init__(self, name: str):
        super().__init__()
        self.name = name

async def simulate_tool_selection():
    print("--- Simulating Agent Tool Selection ---")
    
    # 1. Setup a mock debate cycle
    # We need a debate id, topic, etc.
    debate_id = "test_fred_selection"
    topic = "Discussing the impact of US inflation on global markets"
    
    # Mock agents
    agent_macro = MockAgent("MacroStrategist")
    
    # Create agents in DB if they don't exist
    db = SessionLocal()
    try:
        db_agent = db.query(models.Agent).filter(models.Agent.name == "MacroStrategist").first()
        if not db_agent:
            db_agent = models.Agent(
                name="MacroStrategist", 
                specialty="Macro Economics Specialist",
                system_prompt="You are a macro economist."
            )
            db.add(db_agent)
            db.commit()
            db.refresh(db_agent)
            print(f"Created agent '{db_agent.name}' in DB.")
        
        # 2. Check available tools for this agent
        from api.toolset_service import ToolSetService
        available_tools = ToolSetService.get_agent_available_tools(db, db_agent.id)
        
        print(f"\nAvailable tools for {agent_macro.name}:")
        fred_found = False
        for t in available_tools:
            if t['name'].startswith("fred."):
                print(f"✅ Found: {t['name']} - {t['description']}")
                fred_found = True
        
        if not fred_found:
            print("❌ FRED tools NOT found in available tools list!")
            return

        # 3. Simulate the prompt generation
        # This part requires call_llm_async which we can't easily mock/run without API key
        # but we can check the prompt text.
        
        # We reuse the logic from DebateCycle._agent_select_tools_async
        # (Simplified for checking prompt)
        from api.prompt_service import PromptService
        from api.tool_registry import tool_registry
        
        tools_list_text = "\n".join([f"- {t['name']}: {t['description']}" for t in available_tools if t['name'].startswith("fred.")])
        
        sys_template = PromptService.get_prompt(db, "debate.tool_selection_system")
        if not sys_template: sys_template = "You are {agent_name} on {side} side. Topic: {topic}."
        system_prompt = sys_template.format(agent_name=agent_macro.name, side="pro", topic=topic)

        user_template = PromptService.get_prompt(db, "debate.tool_selection_user")
        if not user_template: user_template = "Select tools from the list:\n{tools_list_text}"
        user_prompt = user_template.format(tools_list_text=tools_list_text)
        
        print("\n--- Generated Prompt Snippet (FRED only) ---")
        print(user_prompt)
        print("\n--- End of Simulation ---")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(simulate_tool_selection())
