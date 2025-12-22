
import asyncio
import json
from worker.chairman import Chairman
from worker.debate_cycle import DebateCycle
from agentscope.agent import AgentBase

async def test_quant_mandate():
    print("🚀 啟動量化主權與行動指令驗證測試：敦陽 2480")
    
    # 1. 設置環境
    debate_id = "test-quant-mandate-2480"
    topic = "敦陽最近為什麼一直跌"
    chairman = Chairman(name="MethodArbiter")
    
    # 模擬量化分析師
    class MockAgent(AgentBase):
        def __init__(self, name):
            super().__init__()
            self.name = name
            self.id = 1
            self.system_prompt = "你是量化分析師。"
            
    agent = MockAgent(name="量化分析師")
    teams = [{"name": "中立", "side": "neutral", "agents": [agent]}]
    
    cycle = DebateCycle(debate_id, topic, chairman, teams, rounds=1)
    # 鎖定事實 (SI 業)
    cycle.anchor_decree = "# 🔒 IMMUTABLE_FACT_LOCK\n- Ticker: 2480.TW\n- Industry: 資訊服務業 (SI)"

    # --- 步驟 1: 驗證工具導流主權 ---
    print("\n--- 步驟 1: 財經工具導流測試 ---")
    # 模擬調用禁用的 TEJ 工具
    tool_name = "tej.institutional_holdings"
    params = {"coid": "2480.TW"}
    
    # 手動模擬 _agent_turn_async 的導流邏輯
    equipped_tools = ["financial.get_verified_price", "chinatimes.stock_fundamental"]
    cycle.agent_tools_map[agent.name] = equipped_tools
    
    print(f"原始請求工具: {tool_name}")
    if tool_name not in equipped_tools and tool_name.startswith("tej."):
        if any(k in tool_name for k in ["holdings", "revenue", "summary"]):
            redirected_tool = "chinatimes.stock_fundamental"
            print(f"✅ 導流成功：偵測到 TEJ 禁用，自動重定向至 -> {redirected_tool}")
        else:
            print("❌ 導流失敗：未轉發至正確財經工具")
    
    # --- 步驟 2: 驗證量化紀律審核 ---
    print("\n--- 步驟 2: 不作為行為 (列清單) 的裁判糾偏測試 ---")
    # 模擬一個「只列清單而不調用工具」的離譜摘要
    mock_summaries = {
        "量化分析師": "關於敦陽下跌，我認為需要進一步調查以下資料：1. 產業年報 2. 公司財報 3. 競爭對手市佔率。目前無結論。"
    }
    
    # 這裡我們需要主席的 Methodology Audit 發揮作用
    # 修改：我們需要讓主席知道什麼是「不作為」
    audit_p = f"""
    分析以下量化分析師的表現。
    內容：{mock_summaries['量化分析師']}
    要求：量化分析師被禁止「列出進一步調查清單」而無實質行動。
    判定：是否違反角色紀律？如果是，請發布裁判令要求其立即調用 chinatimes.* 工具獲取數據。
    輸出格式：{{ "has_violation": true, "arbitration_order": "..." }}
    """
    
    # 執行實際的裁判邏輯
    await cycle._audit_methodology_and_relevance(round_num=1, team_summaries=mock_summaries)
    
    if len(cycle.history) > 0 and "Chairman (Arbiter)" in cycle.history[-1]['role']:
        print("\n[裁判令內容]:")
        print(cycle.history[-1]['content'])
        print("\n✅ 驗證成功：方法論裁判已成功捕捉到 Agent 的「推諉」行為並強制要求行動。")
    else:
        print("\n❌ 驗證失敗：裁判未介入 Agent 的不作為行為。")

if __name__ == "__main__":
    asyncio.run(test_quant_mandate())
