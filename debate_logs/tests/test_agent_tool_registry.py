import unittest
from agent_tool_registry import get_tool, call_tool

class TestAgentToolRegistry(unittest.TestCase):
    def test_twse_tool_registered(self):
        tool = get_tool("twse.price_proof")
        self.assertTrue(callable(tool))

    def test_call_twse_tool_signature(self):
        tool = get_tool("twse.price_proof")
        # Signature requires symbol and asof
        with self.assertRaises(TypeError):
            tool()

if __name__ == "__main__":
    unittest.main()
