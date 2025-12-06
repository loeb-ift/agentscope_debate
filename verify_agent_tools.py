import sys
import json
from worker.debate_cycle import DebateCycle
from worker.chairman import Chairman
from agentscope.agent import AgentBase
from api.tool_registry import tool_registry
from api.init_data import initialize_all
from api.database import SessionLocal
from worker.celery_app import app # Triggers tool registration

def test_scenario(role_name, topic, expected_tool_keywords):
    print(f"\n\n>>> Testing Scenario: [{role_name}] Topic: {topic}")
    
    # 1. Setup Agent
    agent = AgentBase()
    agent.name = role_name
    
    # 2. Setup Cycle (Mocking teams/chairman for context)
    chairman = Chairman(name="Test Chairman")
    
    # Mock Analysis Result to provide context
    mock_analysis = {
        "step5_summary": f"請針對 {topic} 進行深度數據分析。",
        "step6_handcard": "重點：數據驗證"
    }
    
    cycle = DebateCycle(
        debate_id="test", 
        topic=topic, 
        chairman=chairman, 
        teams=[{"name": "TestTeam", "side": "pro", "agents": [agent]}], 
        rounds=1
    )
    cycle.analysis_result = mock_analysis

    # 3. Test Tool Selection
    print("--- Step 1: Tool Selection ---")
    # Force populate registry groups if needed (already done by celery_app import)
    
    cycle._agent_select_tools(agent, "pro")
    selected = cycle.agent_tools_map.get(agent.name, [])
    print(f"Agent Selected: {selected}")
    
    # 4. Test Tool Invocation (Turn)
    print("--- Step 2: Tool Invocation (Thinking) ---")
    # We mock the tool execution to avoid actual API calls if credentials missing, 
    # but we want to see the LLM's *request*.
    # Actually, _agent_turn calls call_llm. We rely on the real LLM here.
    
    response = cycle._agent_turn(agent, "pro", 1)
    
    # Check logs or output
    # Since _agent_turn prints DEBUG logs, we will see the tool call there.
    # We can also check if the expected keywords appear in the output or logs (if captured).
    
    # Simple validation print
    hit = False
    for tool in selected:
        if any(k in tool for k in expected_tool_keywords):
            hit = True
    
    if hit:
        print(f"✅ Tool Selection Success: Selected relevant tools {expected_tool_keywords}")
        
        # Enhanced check for tool invocation params (Checking Time Period)
        if "stock_price" in str(selected) and "start_date" in str(response):
             print("✅ Parameter Check: 'start_date' found in tool call (Time Period handled).")
             # Parse response to check actual dates if possible
             try:
                 import json
                 tool_call = json.loads(response)
                 print(f"   Params: {tool_call.get('params')}")
             except:
                 print(f"   Raw Response: {response[:100]}...")

    else:
        print(f"⚠️ Tool Selection Warning: Did not select expected tools {expected_tool_keywords}. Selected: {selected}")

def main():
    # Ensure DB init
    db = SessionLocal()
    initialize_all(db)
    db.close()

    # Case 1: Quant Analyst -> Stock Price
    test_scenario(
        "量化分析師", 
        "請分析台積電(2330)近半年的股價波動與成交量趨勢",
        ["stock_price"]
    )

    # Case 2: Risk Officer -> Chip Analysis
    test_scenario(
        "風控合規師",
        "請分析鴻海(2317)近期的外資與投信籌碼動向，評估倒貨風險",
        ["institutional_holdings", "foreign_holdings"]
    )

    # Case 3: Valuation Expert -> Financials
    test_scenario(
        "估值專家",
        "請評估聯發科(2454)目前的本益比是否合理，並對比同業營收成長",
        ["financial_summary", "monthly_revenue"]
    )

if __name__ == "__main__":
    main()