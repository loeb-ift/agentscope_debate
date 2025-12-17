
import unittest
from unittest.mock import MagicMock, patch
from adapters.search_router import SearchRouter
from api.quota_service import QuotaService

class TestSearchRouter(unittest.TestCase):
    def setUp(self):
        self.router = SearchRouter()
        self.router.searxng = MagicMock()
        self.router.google = MagicMock()
        
        self.router.searxng.invoke.return_value = {"data": [], "_meta": {"source": "searxng"}}
        self.router.google.invoke.return_value = {"data": [], "_meta": {"source": "google"}}

    @patch("adapters.search_router.quota_service")
    def test_routing_by_role(self, mock_quota):
        # 1. Chairman -> Paid
        mock_quota.check_quota.return_value = True
        
        res = self.router.invoke(q="test", role="chairman")
        self.router.google.invoke.assert_called()
        self.assertEqual(res["_meta"]["router_source"], "google")
        
        # 2. Debater -> Free
        self.router.google.reset_mock()
        res = self.router.invoke(q="test", role="debater")
        self.router.searxng.invoke.assert_called()
        self.assertEqual(res["_meta"]["router_source"], "searxng")

    @patch("adapters.search_router.quota_service")
    def test_quota_limit(self, mock_quota):
        # Chairman -> Paid but Quota Exceeded -> Free
        mock_quota.check_quota.return_value = False
        
        res = self.router.invoke(q="test", role="chairman")
        
        # Verify Fallback
        self.router.searxng.invoke.assert_called()
        self.assertEqual(res["_meta"]["router_source"], "searxng")
        self.assertIn("quota_exceeded", res["_meta"]["router_reason"])

    @patch("adapters.search_router.quota_service")
    def test_explicit_tier(self, mock_quota):
        mock_quota.check_quota.return_value = True
        
        # Debater explicit paid
        res = self.router.invoke(q="test", role="debater", tier="paid")
        self.assertEqual(res["_meta"]["router_source"], "google")
        
        # Chairman explicit free
        res = self.router.invoke(q="test", role="chairman", tier="free")
        self.assertEqual(res["_meta"]["router_source"], "searxng")

if __name__ == "__main__":
    unittest.main()
