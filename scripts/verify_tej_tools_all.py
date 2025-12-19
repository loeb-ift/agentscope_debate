
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from adapters.tej_adapter import (
    TEJCompanyInfo, TEJStockPrice, TEJMonthlyRevenue, 
    TEJInstitutionalHoldings, TEJMarginTrading, TEJForeignHoldings,
    TEJFinancialSummary, TEJFundNAV, TEJShareholderMeeting,
    TEJFundBasicInfo, TEJOffshoreFundInfo, TEJOffshoreFundDividend,
    TEJOffshoreFundHoldingsRegion, TEJOffshoreFundHoldingsIndustry,
    TEJOffshoreFundNAVRank, TEJOffshoreFundNAVDaily, TEJOffshoreFundSuspension,
    TEJOffshoreFundPerformance, TEJIFRSAccountDescriptions, TEJFinancialCoverCumulative,
    TEJFinancialSummaryQuarterly, TEJFinancialCoverQuarterly, TEJFuturesData,
    TEJOptionsBasicInfo, TEJOptionsDailyTrading
)

class TestTEJToolsAvailability(unittest.TestCase):

    def setUp(self):
        # Mock requests.get globally to avoid actual API calls during structure validation
        self.patcher = patch('requests.get')
        self.mock_get = self.patcher.start()
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [], "meta": {}} 
        self.mock_get.return_value = mock_response

        # Common test company ID
        self.test_coid = "2330"

    def tearDown(self):
        self.patcher.stop()

    def _verify_tool(self, tool_class, **kwargs):
        """Helper to verify a tool can be instantiated and invoked correctly."""
        tool_name = tool_class.name
        print(f"Testing {tool_name}...", end=" ")
        
        try:
            adapter = tool_class(api_key="TEST_KEY")
            
            # 1. Test Normal Invocation
            result = adapter.invoke(**kwargs)
            self.assertIsNotNone(result)
            
            # 2. Test Nested Params Invocation (Simulating Agent Error)
            nested_kwargs = {
                "params": kwargs,
                "tool": tool_name
            }
            adapter.invoke(**nested_kwargs)
            
            print("OK")
            return True
        except Exception as e:
            print(f"FAILED: {e}")
            return False

    def test_company_info(self):
        self._verify_tool(TEJCompanyInfo, coid=self.test_coid)

    def test_stock_price(self):
        self._verify_tool(TEJStockPrice, coid=self.test_coid, start_date="2023-01-01", end_date="2023-01-10")

    def test_monthly_revenue(self):
        self._verify_tool(TEJMonthlyRevenue, coid=self.test_coid, start_date="2023-01-01", end_date="2023-06-01")

    def test_institutional_holdings(self):
        self._verify_tool(TEJInstitutionalHoldings, coid=self.test_coid)

    def test_margin_trading(self):
        self._verify_tool(TEJMarginTrading, coid=self.test_coid)

    def test_foreign_holdings(self):
        self._verify_tool(TEJForeignHoldings, coid=self.test_coid)

    def test_financial_summary(self):
        self._verify_tool(TEJFinancialSummary, coid=self.test_coid)
        
    def test_financial_summary_quarterly(self):
        self._verify_tool(TEJFinancialSummaryQuarterly, coid=self.test_coid)

    def test_fund_nav(self):
        # Using a dummy fund ID logic if needed, but 2330 works for mock
        self._verify_tool(TEJFundNAV, coid="0050") 

    def test_shareholder_meeting(self):
        self._verify_tool(TEJShareholderMeeting, coid=self.test_coid)

    def test_fund_basic_info(self):
        self._verify_tool(TEJFundBasicInfo, coid="0050")

    def test_offshore_fund_info(self):
        self._verify_tool(TEJOffshoreFundInfo, coid="F0001")

    def test_offshore_fund_dividend(self):
        self._verify_tool(TEJOffshoreFundDividend, coid="F0001")

    def test_offshore_fund_holdings_region(self):
        self._verify_tool(TEJOffshoreFundHoldingsRegion, coid="F0001")

    def test_offshore_fund_holdings_industry(self):
        self._verify_tool(TEJOffshoreFundHoldingsIndustry, coid="F0001")

    def test_offshore_fund_nav_rank(self):
        self._verify_tool(TEJOffshoreFundNAVRank, coid="F0001")

    def test_offshore_fund_nav_daily(self):
        self._verify_tool(TEJOffshoreFundNAVDaily, coid="F0001")

    def test_offshore_fund_suspension(self):
        self._verify_tool(TEJOffshoreFundSuspension, coid="F0001")

    def test_offshore_fund_performance(self):
        self._verify_tool(TEJOffshoreFundPerformance, coid="F0001")

    def test_ifrs_account_descriptions(self):
        self._verify_tool(TEJIFRSAccountDescriptions, code="1100")

    def test_financial_cover_cumulative(self):
        self._verify_tool(TEJFinancialCoverCumulative, coid=self.test_coid)

    def test_financial_cover_quarterly(self):
        self._verify_tool(TEJFinancialCoverQuarterly, coid=self.test_coid)

    def test_futures_data(self):
        self._verify_tool(TEJFuturesData, coid="TXF")

    def test_options_basic_info(self):
        self._verify_tool(TEJOptionsBasicInfo, coid="TXO")

    def test_options_daily_trading(self):
        self._verify_tool(TEJOptionsDailyTrading, coid="TXO")

if __name__ == "__main__":
    unittest.main()
