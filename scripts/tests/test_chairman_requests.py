import unittest
from unittest.mock import patch, MagicMock
import os
import json
from worker.chairman import Chairman

class TestChairmanRequests(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"CHAIRMAN_FACILITATION": "1"})
    @patch("worker.chairman_facilitation.get_redis_client")
    async def test_publish_requests_event(self, mock_get_redis):
        """
        Verify that publish_requests emits ChairmanRequestsPublished event.
        """
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        chairman = Chairman(name="Chair", model_config_name="gpt-4")
        debate_id = "test_debate_002"
        
        requests = [
            {"target": "AgentPro", "instruction": "Clarify definitions"},
            {"target": "AgentCon", "instruction": "Provide counter-evidence"}
        ]
        
        await chairman.publish_requests(debate_id, requests)
        
        # Verify Redis Publish
        mock_redis.publish.assert_called_once()
        channel, message = mock_redis.publish.call_args[0]
        
        self.assertEqual(channel, f"debate:{debate_id}:log_stream")
        
        event_data = json.loads(message)
        self.assertEqual(event_data["type"], "ChairmanRequestsPublished")
        self.assertEqual(event_data["payload"]["request_count"], 2)
        self.assertEqual(event_data["payload"]["requests"][0]["target"], "AgentPro")

if __name__ == "__main__":
    unittest.main()
