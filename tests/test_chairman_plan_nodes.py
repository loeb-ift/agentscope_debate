import unittest
from unittest.mock import patch, MagicMock
import os
import json
from worker.chairman import Chairman

class TestChairmanPlanNodes(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"CHAIRMAN_FACILITATION": "1"})
    @patch("worker.chairman_facilitation.get_redis_client")
    async def test_generate_plan_nodes_event(self, mock_get_redis):
        """
        Verify that generate_plan_nodes emits ChairmanRequestsPublished event with correct payload.
        """
        # Setup Mock Redis
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        # Init Chairman
        chairman = Chairman(name="Chair", model_config_name="gpt-4") # kwargs might vary
        
        debate_id = "test_debate_001"
        context = {"trace_id": "tr-111", "topic": "AI Future"}
        
        # Execute
        nodes = await chairman.generate_plan_nodes(debate_id, context)
        
        # Assertions
        self.assertIsInstance(nodes, list)
        self.assertGreater(len(nodes), 0)
        
        # Verify Redis Publish
        mock_redis.publish.assert_called_once()
        channel, message = mock_redis.publish.call_args[0]
        
        self.assertEqual(channel, f"debate:{debate_id}:log_stream")
        
        event_data = json.loads(message)
        self.assertEqual(event_data["type"], "ChairmanRequestsPublished")
        self.assertEqual(event_data["role"], "Chairman (System)")
        self.assertIn("plan_nodes", event_data["payload"])
        self.assertEqual(event_data["payload"]["trace_id"], "tr-111")
        
        # Verify History Push
        mock_redis.rpush.assert_called_once()

if __name__ == "__main__":
    unittest.main()
