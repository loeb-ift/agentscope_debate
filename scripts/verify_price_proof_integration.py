import unittest
from unittest.mock import MagicMock, patch
import asyncio
from worker.utils.price_proof_coordinator import PriceProofCoordinator
from adapters.integration.tej_price_client import TejPriceClient
from adapters.twse_adapter import TWSEStockDay
from adapters.yahoo_adapter import YahooPriceAdapter

class TestPriceProofIntegration(unittest.TestCase):
    def setUp(self):
        self.coordinator = PriceProofCoordinator()

    @patch.object(TejPriceClient, 'get_price')
    def test_tej_success(self, mock_tej):
        """Test happy path: TEJ returns data"""
        print("\n=== Test 1: TEJ Success ===")
        mock_tej.return_value = {
            "source": "TEJ",
            "symbol": "2330",
            "count": 1,
            "data": [{"date": "2024-01-01", "close": 600.0}]
        }
        
        result = self.coordinator.get_verified_price("2330", "2024-01-01")
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "TEJ (Primary)")
        self.assertEqual(result["price"], 600.0)
        print("✅ TEJ Success verified")

    @patch.object(TejPriceClient, 'get_price')
    @patch.object(TWSEStockDay, 'invoke')
    def test_fallback_to_twse(self, mock_twse, mock_tej):
        """Test fallback: TEJ empty -> TWSE success"""
        print("\n=== Test 2: Fallback to TWSE ===")
        # TEJ returns empty
        mock_tej.return_value = {"source": "TEJ", "data": [], "message": "Empty"}
        
        # TWSE returns data
        mock_twse.return_value = {
            "data": [
                {"date": "2024-01-01", "close": 605.0},
                {"date": "2023-12-29", "close": 595.0}
            ]
        }
        
        result = self.coordinator.get_verified_price("2330", "2024-01-01")
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "TWSE (Official Backup)")
        self.assertEqual(result["price"], 605.0)
        self.assertTrue(result["fallback_used"])
        print("✅ Fallback to TWSE verified")

    @patch.object(TejPriceClient, 'get_price')
    @patch.object(TWSEStockDay, 'invoke')
    @patch.object(YahooPriceAdapter, 'invoke')
    def test_fallback_to_yahoo(self, mock_yahoo, mock_twse, mock_tej):
        """Test fallback: TEJ empty -> TWSE empty -> Yahoo success"""
        print("\n=== Test 3: Fallback to Yahoo ===")
        # TEJ empty
        mock_tej.return_value = {"source": "TEJ", "data": []}
        # TWSE empty
        mock_twse.return_value = {"data": []}
        # Yahoo success
        mock_yahoo.return_value = {
            "data": [{"date": "2024-01-01", "close": 610.0}]
        }
        
        result = self.coordinator.get_verified_price("2330", "2024-01-01")
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "Yahoo Finance (External Backup)")
        self.assertEqual(result["price"], 610.0)
        print("✅ Fallback to Yahoo verified")

    @patch.object(TejPriceClient, 'get_price')
    @patch.object(TWSEStockDay, 'invoke')
    @patch.object(YahooPriceAdapter, 'invoke')
    def test_all_fail(self, mock_yahoo, mock_twse, mock_tej):
        """Test failure: All sources empty"""
        print("\n=== Test 4: All Sources Failed ===")
        mock_tej.return_value = {"source": "TEJ", "data": []}
        mock_twse.return_value = {"data": []}
        mock_yahoo.return_value = {"data": []}
        
        result = self.coordinator.get_verified_price("2330", "2024-01-01")
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)
        print("✅ All Failure verified")

if __name__ == '__main__':
    unittest.main()