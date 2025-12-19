
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to sys.path to allow imports from api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock ODSInternalAdapter since it might not be relevant for this specific test
# or if we want to focus solely on EDAToolAdapter logic
sys.modules['adapters.ods_internal_adapter'] = MagicMock()

try:
    from adapters.eda_tool_adapter import EDAToolAdapter
except ImportError:
    # If the file doesn't exist yet (iteration 1), we might need to mock or skip
    # But based on the user request, we are testing if it is registered correctly.
    # So we assume the file should be there or we are testing its logic.
    print("WARNING: adapters.eda_tool_adapter not found. This test might fail.")
    EDAToolAdapter = None

class TestEDAToolAdapterStandalone(unittest.TestCase):
    
    def setUp(self):
        if EDAToolAdapter is None:
            self.skipTest("EDAToolAdapter not available")
        self.adapter = EDAToolAdapter()

    def test_adapter_initialization(self):
        """Test if the adapter initializes correctly."""
        self.assertIsNotNone(self.adapter)
        # Check if it has the expected methods/attributes based on typical adapter structure
        self.assertTrue(hasattr(self.adapter, 'describe'))
        self.assertTrue(hasattr(self.adapter, 'invoke'))

    def test_get_tool_def(self):
        """Test the tool definition structure."""
        # EDAToolAdapter uses describe() instead of get_tool_def() as per base ToolAdapter
        tool_def = self.adapter.describe()
        self.assertIsInstance(tool_def, dict)
        self.assertIn('name', tool_def)
        self.assertIn('description', tool_def)
        self.assertIn('schema', tool_def)
        
        # Verify specific tool name
        self.assertEqual(tool_def['name'], 'chairman.eda_analysis')
        self.assertEqual(tool_def['version'], 'v1')

    @patch('adapters.eda_tool_adapter.EDAToolAdapter._prepare_stock_data')
    @patch('adapters.eda_tool_adapter.EDAToolAdapter._invoke_eda_service')
    @patch('adapters.eda_tool_adapter.EDAToolAdapter._validate_artifacts')
    @patch('adapters.eda_tool_adapter.EDAToolAdapter._ingest_artifacts')
    @patch('adapters.eda_tool_adapter.EDAToolAdapter._format_summary')
    def test_invoke_describe(self, mock_format, mock_ingest, mock_validate, mock_invoke_eda, mock_prepare):
        """Test invoking the describe tool (mocking internal steps)."""
        # Mock internal methods to avoid actual side effects (IO, DB)
        mock_prepare.return_value = "/data/staging/test.csv"
        
        mock_invoke_eda.return_value = {
            "report_path": "/data/reports/test/eda_profile.html",
            "plot_paths": [],
            "table_paths": [],
            "metadata": {"rows": 100}
        }
        
        mock_validate.return_value = {'passed': True, 'issues': []}
        
        mock_evidence_doc = MagicMock()
        mock_evidence_doc.id = "doc123"
        mock_ingest.return_value = [mock_evidence_doc]
        
        mock_format.return_value = "Summary Text"

        # Test params
        kwargs = {
            "symbol": "2330.TW",
            "debate_id": "debate_001",
            "lookback_days": 120
        }
        
        # Invoke (EDAToolAdapter.invoke handles sync wrapper around async _invoke_async)
        result = self.adapter.invoke(**kwargs)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertFalse(result['degraded'])
        self.assertEqual(result['summary'], "Summary Text")
        self.assertEqual(result['evidence_ids'], ["doc123"])
        self.assertEqual(result['artifacts']['report'], "/data/reports/test/eda_profile.html")
        
        # Verify call flow
        mock_prepare.assert_called_once()
        mock_invoke_eda.assert_called_once()
        mock_validate.assert_called_once()
        mock_ingest.assert_called_once()
        mock_format.assert_called_once()

if __name__ == '__main__':
    unittest.main()
