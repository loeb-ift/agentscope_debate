import unittest
from unittest.mock import patch, MagicMock
import os
import json
from worker.chairman import Chairman

class TestChairmanModeSwitch(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"CHAIRMAN_FACILITATION": "1"})
    @patch("worker.chairman_facilitation.get_redis_client")
    async def test_detect_mode_switch_triggered(self, mock_get_redis):
        """
        Verify that detect_mode_switch emits ChairmanModeSwitch event when triggered.
        """
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        chairman = Chairman(name="Chair", model_config_name="gpt-4")
        debate_id = "test_debate_003"
        
        # Scenario: Trigger switch
        state = {"ranking_triggered": True, "consensus_score": 0.9}
        
        mode = await chairman.detect_mode_switch(debate_id, state)
        
        self.assertEqual(mode, "ranking_debate")
        
        # Verify Redis Publish
        mock_redis.publish.assert_called_once()
        channel, message = mock_redis.publish.call_args[0]
        
        event_data = json.loads(message)
        self.assertEqual(event_data["type"], "ChairmanModeSwitch")
        self.assertEqual(event_data["payload"]["to_mode"], "ranking_debate")
        self.assertIn("rationale", event_data["payload"])

    @patch.dict(os.environ, {"CHAIRMAN_FACILITATION": "1"})
    @patch("worker.chairman_facilitation.get_redis_client")
    async def test_detect_mode_switch_no_trigger(self, mock_get_redis):
        """
        Verify that no event is emitted if no switch is needed.
        """
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        chairman = Chairman(name="Chair", model_config_name="gpt-4")
        state = {"ranking_triggered": False}
        
        mode = await chairman.detect_mode_switch("debate_id", state)
        
        self.assertEqual(mode, "normal")
        mock_redis.publish.assert_not_called()

if __name__ == "__main__":
    unittest.main()
