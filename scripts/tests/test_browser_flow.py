
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from worker.debate_cycle import DebateCycle
from api.tool_registry import tool_registry

class TestBrowserFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock DebateCycle initialization
        self.debate_id = "test_debate_123"
        self.topic = "台積電 2024 年發展前景"
        
        with patch('worker.debate_cycle.SessionLocal'):
             with patch('worker.debate_cycle.ReMeHistoryMemory'):
                  with patch('worker.debate_cycle.HippocampalMemory'):
                       self.cycle = DebateCycle(self.debate_id, self.topic, MagicMock(), [], 3)
        
        # Mock publish log to avoid Redis dependency in test
        self.cycle._publish_log = MagicMock()

    @patch('worker.debate_cycle.call_llm_async')
    async def test_chairman_approval_gate(self, mock_llm):
        """測試主席准許機制"""
        # Mock Chairman's positive response
        mock_llm.return_value = json.dumps({
            "approved": True,
            "reason": "由於該網頁包含台積電法說會原始摘要，具有高度邊際效益。",
            "guidance": "請專注於毛利率與資本支出部分的分析。"
        })
        
        agent = MagicMock()
        agent.name = "Analyst"
        tool_name = "browser.browse"
        params = {"url": "https://example.com/tsmc", "justification": "查核台積電最新指引"}
        
        decision = await self.cycle._request_chairman_tool_approval(agent, tool_name, params)
        
        self.assertTrue(decision["approved"])
        self.cycle._publish_log.assert_any_call("Governance", "🛡️ 攔截到受限工具調用：browser.browse。正在請求主席核准...")
        print("✅ 主主席審核攔截測試通過")

    @patch('worker.debate_cycle.call_llm_async')
    async def test_summarization_logic(self, mock_llm):
        """測試記憶管理：自動摘要"""
        # Mock LLM summarization response
        mock_llm.return_value = "這是摘要後的內容，保留了核心數據。"
        
        large_content = "台積電" * 1000 # 3000 chars
        tool_name = "browser.browse"
        
        summarized = await self.cycle._summarize_content(large_content, tool_name)
        
        self.assertIn("摘要後的內容", summarized)
        self.assertIn("原始長度：3000", summarized)
        self.cycle._publish_log.assert_any_call("System", "🧠 正在為工具 browser.browse 的龐大結果進行優化與摘要...")
        print("✅ 記憶優化摘要測試通過")

    async def test_gated_execution_flow(self):
        """模擬完整 _agent_turn_async 中的攔截邏輯"""
        # 我們不跑完整 turn，僅手動測試我們插入的邏輯區塊
        tool_name = "browser.browse"
        
        # 模擬 registry 中該工具標記為 requires_approval
        tool_meta = tool_registry.get_tool_data(tool_name)
        self.assertTrue(tool_meta.get("requires_approval"))
        
        print(f"✅ 工具 {tool_name}requires_approval 標記確認正確")

if __name__ == "__main__":
    unittest.main()
