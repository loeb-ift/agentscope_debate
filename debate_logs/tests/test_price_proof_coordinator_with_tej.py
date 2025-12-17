import os
import unittest
import datetime as dt

from price_proof_coordinator import get_price_proof


@unittest.skipUnless(bool(os.getenv('TEJ_API_KEY')), 'TEJ_API_KEY not set; skipping live TEJ test')
class TestPriceProofCoordinatorWithTEJ(unittest.TestCase):
    def setUp(self):
        # Prefer disabling SSL verify for TWSE in CI-like envs if needed
        os.environ.setdefault('TWSE_VERIFY_SSL', 'false')

    def test_three_sources_2330_weekend(self):
        # 2330.TW, weekend date for fallback behavior
        result = get_price_proof('2330.TW', '2025-12-13')
        self.assertIn('success', result)
        self.assertTrue(result['success'])
        self.assertIn(result['source'], ['TEJ', 'TWSE', 'Yahoo'])
        self.assertIsNotNone(result['trade_date'])
        self.assertLessEqual(result['trade_date'], '2025-12-13')
        # Expect some form of cross-checks if source is TEJ or TWSE
        if result['source'] in ('TEJ', 'TWSE'):
            self.assertIn('cross_checks', result)
        # Data row sanity
        row = result['row']
        self.assertIsNotNone(row)
        for k in ('open', 'high', 'low', 'close'):
            self.assertIn(k, row)


if __name__ == '__main__':
    unittest.main()
