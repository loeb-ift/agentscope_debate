import unittest
from datetime import date
from worker.utils.price_proof_coordinator import normalize_symbol

class TestPriceProofParams(unittest.TestCase):
    
    def test_normalize_symbol_tw(self):
        # Case 1: Standard TWSE code "2330"
        res = normalize_symbol("2330")
        self.assertEqual(res['coid'], "2330")
        self.assertEqual(res['yahoo_ticker'], "2330.TW")
        
        # Case 2: Yahoo format "2330.TW"
        res = normalize_symbol("2330.TW")
        self.assertEqual(res['coid'], "2330")
        self.assertEqual(res['yahoo_ticker'], "2330.TW")
        
        # Case 3: Prefix format "TW:2330"
        res = normalize_symbol("TW:2330")
        self.assertEqual(res['coid'], "2330")
        self.assertEqual(res['yahoo_ticker'], "2330.TW")

    def test_date_formatting_logic(self):
        # Simulate logic inside coordinator
        asof = date(2024, 11, 1)
        
        # TWSE needs YYYYMMDD
        twse_date = asof.strftime("%Y%m%d")
        self.assertEqual(twse_date, "20241101")
        
        # TEJ needs YYYY-MM-DD
        tej_date = asof.strftime("%Y-%m-%d")
        self.assertEqual(tej_date, "2024-11-01")

if __name__ == '__main__':
    unittest.main()