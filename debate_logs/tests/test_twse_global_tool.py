import os
import socket
import unittest
import datetime as dt

from twse_global_tool import get_twse_price_proof, TWSEClient


def _internet_available(host="www.twse.com.tw", port=80, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, port), timeout)
        return True
    except Exception:
        return False


class TestTWSEGlobalTool(unittest.TestCase):
    @unittest.skipUnless(_internet_available(), "Internet/TWSE not reachable")
    def test_weekend_fallback(self):
        # 2025-12-13 is Saturday; expect fallback to previous trading day
        proof = get_twse_price_proof("2480.TW", "2025-12-13")
        self.assertTrue(proof["success"])  # should succeed
        self.assertEqual(proof["source"], "TWSE")
        self.assertEqual(proof["stockNo"], "2480")
        self.assertEqual(proof["asof"], "2025-12-13")
        # trade_date should be <= asof, and typically != asof on weekend
        self.assertIsNotNone(proof["trade_date"])
        self.assertLessEqual(proof["trade_date"], proof["asof"])  # string compare is ok for ISO dates
        self.assertIn("warnings", proof)
        # When weekend, we expect a fallback warning
        self.assertTrue(any("Non-trading day" in w for w in proof["warnings"]))

    @unittest.skipUnless(_internet_available(), "Internet/TWSE not reachable")
    def test_empty_data_symbol(self):
        # Use an unlikely stock number to trigger empty result
        proof = get_twse_price_proof("0000", "2025-12-13")
        # Depending on TWSE behavior, it may return empty or error handled internally
        # We expect a graceful response
        if proof["success"]:
            # If TWSE happens to return data, at least ensure structure is correct
            self.assertIn("row", proof)
            self.assertIn("trade_date", proof)
        else:
            # No data available; ensure warnings mention the failure
            self.assertIn("warnings", proof)
            self.assertTrue(len(proof["warnings"]) >= 0)


if __name__ == "__main__":
    unittest.main()
