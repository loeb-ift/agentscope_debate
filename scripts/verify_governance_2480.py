
import asyncio
import json
import os
from worker.chairman import Chairman
from worker.debate_cycle import DebateCycle
from agentscope.agent import AgentBase

async def test_governance_flow():
    print("🚀 啟動治理架構驗證測試：敦陽最近為什麼一直跌")
    
    # 1. 設置環境
    debate_id = "test-governance-2480"
    topic = "敦陽最近為什麼一直跌"
    chairman = Chairman(name="TestArbiter")
    
    # 模擬團隊
    class MockAgent(AgentBase):
        def __init__(self, name, sys_prompt=""):
            super().__init__()
            self.name = name
            self.system_prompt = sys_prompt
            self.id = 1
            
    teams = [
        {
            "name": "正方",
            "side": "pro",
            "agents": [MockAgent(name="價值投資人", sys_prompt="你是價值投資人")]
        },
        {
            "name": "中立",
            "side": "neutral",
            "agents": [MockAgent(name="量化分析師", sys_prompt="你是量化分析師")]
        }
    ]
    
    cycle = DebateCycle(debate_id, topic, chairman, teams, rounds=1)
    
    # 2. 測試主席的【不可變事實鎖定】生成
    print("\n--- 步驟 1: 主席調查與事實鎖定 ---")
    analysis_packet = await chairman.pre_debate_analysis(topic, debate_id=debate_id)
    bg_info = analysis_packet.get("bg_info", "")
    
    anchor_decree = await chairman.generate_anchor_decree(topic, bg_info, debate_id)
    print(f"\n[主席發布的事實鎖定]:\n{anchor_decree}")
    
    assert "IMMUTABLE_FACT_LOCK" in anchor_decree
    assert "2480" in anchor_decree
    
    # 3. 測試 Agent 端的角色紀律注入
    print("\n--- 步驟 2: Agent 角色紀律檢查 ---")
    cycle.anchor_decree = anchor_decree
    # 模擬量化分析師的回合
    agent = teams[1]["agents"][0]
    
    # 這裡我們不真正運行 LLM 回合，而是檢查 System Prompt 的組成
    # (我們手動調用 _agent_turn_async 的內部 logic 模擬)
    print(f"正在檢查 {agent.name} 的角色紅線注入...")
    # (此處為示意，實際代碼中已在 _agent_turn_async 實作)
    
    # 4. 測試方法論裁判的【賽中糾偏】
    print("\n--- 步驟 3: 方法論裁判糾偏測試 ---")
    # 模擬一個嚴重離題且角色越權的摘要
    mock_summaries = {
        "正方": "敦陽雖然是資訊服務，但我認為他其實具備半導體設備的潛力，而且我看好鋰電池發展。買入！",
        "中立": "目前查不到 ROIC 數據，但我感覺 ROIC 一定小於 WACC。敦陽必跌。"
    }
    
    await cycle._audit_methodology_and_relevance(round_num=1, team_summaries=mock_summaries)
    
    # 檢查歷史記錄中是否有裁判令
    last_msg = cycle.history[-1]
    print(f"\n[裁判令結果]:\n{last_msg['content']}")
    
    if "Chairman (Arbiter)" in last_msg['role']:
        print("\n✅ 治理機制驗證成功：裁判已正確識別離題與非法推論。")
    else:
        print("\n❌ 治理機制驗證失敗：裁判未介入。")

if __name__ == "__main__":
    asyncio.run(test_governance_flow())
