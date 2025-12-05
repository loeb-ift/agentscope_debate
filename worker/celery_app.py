import sys
sys.path.insert(0, '/app')

from celery import Celery
from dotenv import load_dotenv
import os

from api.database import init_db
from adapters.searxng_adapter import SearXNGAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.yfinance_adapter import YFinanceAdapter
from adapters.tej_adapter import (
    TEJCompanyInfo, TEJStockPrice, TEJMonthlyRevenue, TEJInstitutionalHoldings,
    TEJMarginTrading, TEJForeignHoldings, TEJFinancialSummary, TEJFundNAV,
    TEJShareholderMeeting, TEJFundBasicInfo, TEJOffshoreFundInfo, TEJOffshoreFundDividend,
    TEJOffshoreFundHoldingsRegion, TEJOffshoreFundHoldingsIndustry, TEJOffshoreFundNAVRank,
    TEJOffshoreFundNAVDaily, TEJOffshoreFundSuspension, TEJOffshoreFundPerformance,
    TEJIFRSAccountDescriptions, TEJFinancialCoverCumulative, TEJFinancialSummaryQuarterly,
    TEJFinancialCoverQuarterly, TEJFuturesData, TEJOptionsBasicInfo, TEJOptionsDailyTrading
)
from api.tool_registry import tool_registry

load_dotenv()

# 建立 Celery 實例
redis_host = os.getenv('REDIS_HOST', 'localhost')
app = Celery('worker', broker=f'redis://{redis_host}:6379/0', backend=f'redis://{redis_host}:6379/0')
app.autodiscover_tasks(['worker'])

# 在 worker 啟動時註冊工具
tool_registry.register(SearXNGAdapter())
tool_registry.register(DuckDuckGoAdapter())
tool_registry.register(YFinanceAdapter())
tool_registry.register(TEJCompanyInfo())
tool_registry.register(TEJStockPrice())
tool_registry.register(TEJMonthlyRevenue())
tool_registry.register(TEJInstitutionalHoldings())
tool_registry.register(TEJMarginTrading())
tool_registry.register(TEJForeignHoldings())
tool_registry.register(TEJFinancialSummary())
tool_registry.register(TEJFundNAV())
tool_registry.register(TEJShareholderMeeting())
tool_registry.register(TEJFundBasicInfo())
tool_registry.register(TEJOffshoreFundInfo())
tool_registry.register(TEJOffshoreFundDividend())
tool_registry.register(TEJOffshoreFundHoldingsRegion())
tool_registry.register(TEJOffshoreFundHoldingsIndustry())
tool_registry.register(TEJOffshoreFundNAVRank())
tool_registry.register(TEJOffshoreFundNAVDaily())
tool_registry.register(TEJOffshoreFundSuspension())
tool_registry.register(TEJOffshoreFundPerformance())
tool_registry.register(TEJIFRSAccountDescriptions())
tool_registry.register(TEJFinancialCoverCumulative())
tool_registry.register(TEJFinancialSummaryQuarterly())
tool_registry.register(TEJFinancialCoverQuarterly())
tool_registry.register(TEJFuturesData())
tool_registry.register(TEJOptionsBasicInfo())
tool_registry.register(TEJOptionsDailyTrading())

# 在 worker 啟動時初始化資料庫
init_db()

