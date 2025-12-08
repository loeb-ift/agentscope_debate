import sys
sys.path.insert(0, '/app')

from celery import Celery
from dotenv import load_dotenv
import os

from api.database import init_db, SessionLocal
from api import models
from api.init_data import initialize_all
from adapters.http_tool_adapter import HTTPToolAdapter
from adapters.python_tool_adapter import PythonToolAdapter
from adapters.searxng_adapter import SearXNGAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.database_tool_adapter import SearchCompany, GetCompanyDetails, GetSecurityDetails
from adapters.internal_terms_adapter import InternalTermLookup, InternalTermExplain
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
from adapters.web_fetch_adapter import WebFetchAdapter
from api.tool_registry import tool_registry

load_dotenv()

# 建立 Celery 實例
redis_host = os.getenv('REDIS_HOST', 'localhost')
app = Celery('worker', broker=f'redis://{redis_host}:6379/0', backend=f'redis://{redis_host}:6379/0')
app.autodiscover_tasks(['worker'])

# 在 worker 啟動時註冊工具
# Browser Use Group
tool_registry.register(SearXNGAdapter(), group="browser_use")
tool_registry.register(DuckDuckGoAdapter(), group="browser_use")
tool_registry.register(WebFetchAdapter(), group="browser_use")

# Financial Data Group
tool_registry.register(YFinanceAdapter(), group="financial_data")
tool_registry.register(TEJCompanyInfo(), group="financial_data")
tool_registry.register(TEJStockPrice(), group="financial_data")
tool_registry.register(TEJMonthlyRevenue(), group="financial_data")
tool_registry.register(TEJInstitutionalHoldings(), group="financial_data")
tool_registry.register(TEJMarginTrading(), group="financial_data")
tool_registry.register(TEJForeignHoldings(), group="financial_data")
tool_registry.register(TEJFinancialSummary(), group="financial_data")
tool_registry.register(TEJFundNAV(), group="financial_data")
tool_registry.register(TEJShareholderMeeting(), group="financial_data")
tool_registry.register(TEJFundBasicInfo(), group="financial_data")
tool_registry.register(TEJOffshoreFundInfo(), group="financial_data")
tool_registry.register(TEJOffshoreFundDividend(), group="financial_data")
tool_registry.register(TEJOffshoreFundHoldingsRegion(), group="financial_data")
tool_registry.register(TEJOffshoreFundHoldingsIndustry(), group="financial_data")
tool_registry.register(TEJOffshoreFundNAVRank(), group="financial_data")
tool_registry.register(TEJOffshoreFundNAVDaily(), group="financial_data")
tool_registry.register(TEJOffshoreFundSuspension(), group="financial_data")
tool_registry.register(TEJOffshoreFundPerformance(), group="financial_data")
tool_registry.register(TEJIFRSAccountDescriptions(), group="financial_data")
tool_registry.register(TEJFinancialCoverCumulative(), group="financial_data")
tool_registry.register(TEJFinancialSummaryQuarterly(), group="financial_data")
tool_registry.register(TEJFinancialCoverQuarterly(), group="financial_data")
tool_registry.register(TEJFuturesData(), group="financial_data")
tool_registry.register(TEJOptionsBasicInfo(), group="financial_data")
tool_registry.register(TEJOptionsDailyTrading(), group="financial_data")

# Internal Data Group
tool_registry.register(SearchCompany(), group="internal_data")
tool_registry.register(GetCompanyDetails(), group="internal_data")
tool_registry.register(GetSecurityDetails(), group="internal_data")
# Internal Terms
tool_registry.register(InternalTermLookup(), group="internal_data")
tool_registry.register(InternalTermExplain(), group="internal_data")

# 在 worker 啟動時初始化資料庫與數據
init_db()

db = SessionLocal()
try:
    initialize_all(db)
finally:
    db.close()

# 加載用戶定義的工具 (Dynamic Tools)
db = SessionLocal()
try:
    custom_tools = db.query(models.Tool).filter(models.Tool.enabled == True).all()
    print(f"Loading {len(custom_tools)} custom tools from database...")
    for tool in custom_tools:
        try:
            adapter = None
            if tool.type == 'http':
                adapter = HTTPToolAdapter(
                    name=tool.name,
                    description=f"User defined HTTP tool (ID: {tool.id})",
                    api_config=tool.api_config,
                    schema=tool.json_schema
                )
            elif tool.type == 'python':
                adapter = PythonToolAdapter(
                    name=tool.name,
                    description=f"User defined Python tool (ID: {tool.id})",
                    python_code=tool.python_code,
                    schema=tool.json_schema
                )
            
            if adapter:
                tool_registry.register(adapter, group=tool.group)
        except Exception as e:
            print(f"Error registering custom tool {tool.name}: {e}")
finally:
    db.close()

