import unittest
from unittest.mock import patch, MagicMock
import os
import json
from worker.chairman import Chairman

class TestChairmanNoConclusion(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"CHAIRMAN_FACILITATION": "1"})
    @patch("worker.chairman_facilitation.get_redis_client")
    async def test_summarize_without_conclusion_event(self, mock_get_redis):
        """
        Verify that summarize_without_conclusion emits ChairmanDecisionLog event.
        """
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        chairman = Chairman(name="Chair", model_config_name="gpt-4")
        debate_id = "test_debate_004"
        
        process_data = {
            "coverage": 0.75,
            "issues": ["Citation missing in Claim 2"]
        }
        
        await chairman.summarize_without_conclusion(debate_id, process_data)
        
        # Verify Redis Publish
        mock_redis.publish.assert_called_once()
        event_data = json.loads(mock_redis.publish.call_args[0][1])
        
        self.assertEqual(event_data["type"], "ChairmanDecisionLog")
        self.assertEqual(event_data["payload"]["summary_type"], "procedural_summary")
        self.assertEqual(event_data["payload"]["coverage"], 0.75)

if __name__ == "__main__":
    unittest.main()
