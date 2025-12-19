
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from worker.debate_cycle import DebateCycle
from api.tool_registry import tool_registry

class TestBrowserGovernance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock DebateCycle initialization
        self.debate_id = "test_debate_治理驗證"
        self.topic = "測試瀏覽器治理機制"
        
        with patch('worker.debate_cycle.SessionLocal'):
             with patch('worker.debate_cycle.ReMeHistoryMemory'):
                  with patch('worker.debate_cycle.HippocampalMemory'):
                       self.cycle = DebateCycle(self.debate_id, self.topic, MagicMock(), [], 3)
        
        # Mock publish log to avoid Redis dependency in test
        self.cycle._publish_log = MagicMock()

    def test_url_extraction(self):
        """測試 URL 提取 Helper"""
        text = "請查看這個連結：https://tsmc.com/news.html 以及 http://example.org/data?id=123"
        urls = self.cycle._extract_urls(text)
        self.assertIn("https://tsmc.com/news.html", urls)
        self.assertIn("http://example.org/data?id=123", urls)
        print("✅ URL 提取測試通過")

    async def test_quota_and_discovery_rejection(self):
        """測試無配額或未搜尋網址的自動駁回"""
        agent = MagicMock()
        agent.name = "TestAgent"
        
        # 1. 初始狀態配額應為 0
        self.assertEqual(self.cycle.browse_quota, 0)
        
        # 2. 嘗試調用 (無配額)
        res = await self.cycle._request_chairman_tool_approval(agent, "browser.browse", {"url": "https://unknown.com"})
        self.assertFalse(res["approved"])
        self.assertEqual(res["reason"], "無瀏覽配額")
        print("✅ 無配額攔截測試通過")
        
        # 3. 模擬搜尋增加配額，但調用非白名單網址
        self.cycle.browse_quota = 1
        res = await self.cycle._request_chairman_tool_approval(agent, "browser.browse", {"url": "https://not-in-list.com"})
        self.assertFalse(res["approved"])
        self.assertEqual(res["reason"], "網址未經搜尋發現")
        print("✅ 非白名單網址攔截測試通過")

    @patch('worker.debate_cycle.call_llm_async')
    async def test_successful_governance_flow(self, mock_llm):
        """測試完整成功流程：搜尋發現 -> 申請 -> 主席核准 -> 扣除配額"""
        agent = MagicMock()
        agent.name = "Strategist"
        
        # 1. 模擬搜尋結果
        search_result = "搜尋到台積電官網：https://www.tsmc.com/chinese"
        found = self.cycle._extract_urls(search_result)
        self.cycle.discovered_urls.update(found)
        self.cycle.browse_quota += 1
        
        self.assertIn("https://www.tsmc.com/chinese", self.cycle.discovered_urls)
        self.assertEqual(self.cycle.browse_quota, 1)
        
        # 2. 主席 Mock 核准
        mock_llm.return_value = json.dumps({
            "approved": True,
            "reason": "該連結來自搜尋結果且具有高度參考價值。",
            "guidance": "請重點分析資本支出項目。"
        })
        
        # 3. 發起調用
        params = {"url": "https://www.tsmc.com/chinese", "justification": "分析最新法說會指引"}
        res = await self.cycle._request_chairman_tool_approval(agent, "browser.browse", params)
        
        self.assertTrue(res["approved"])
        self.assertEqual(self.cycle.browse_quota, 0) # 配額應被扣除
        print("✅ 完整治理流程 (搜尋->准核->扣除) 測試通過")

if __name__ == "__main__":
    unittest.main()
