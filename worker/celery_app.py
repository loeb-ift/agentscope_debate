import sys
sys.path.insert(0, '/app')

from celery import Celery
from dotenv import load_dotenv
import os

from api.database import init_db, SessionLocal
from api import models
from api.init_data import initialize_all
from api.config import Config
# Lazy import wrappers
def lazy_import_factory(module_name, class_name):
    def factory():
        import importlib
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        return cls()
    return factory
from api.tool_registry import tool_registry

load_dotenv()

# 建立 Celery 實例
app = Celery('worker', broker=Config.REDIS_URL, backend=Config.REDIS_URL)
app.autodiscover_tasks(['worker'])

# 在 worker 啟動時註冊工具
# Browser Use Group
tool_registry.register_lazy("searxng.search", lazy_import_factory("adapters.searxng_adapter", "SearXNGAdapter"), group="browser_use", description="Search Engine")
tool_registry.register_lazy("duckduckgo.search", lazy_import_factory("adapters.duckduckgo_adapter", "DuckDuckGoAdapter"), group="browser_use", description="DuckDuckGo Search")
tool_registry.register_lazy("web.fetch", lazy_import_factory("adapters.web_fetch_adapter", "WebFetchAdapter"), group="browser_use", description="Web Fetch")

# Financial Data Group
tool_registry.register_lazy("yfinance.stock_price", lazy_import_factory("adapters.yfinance_adapter", "YFinanceAdapter"), group="financial_data", description="Yahoo Finance")

# TEJ Tools
tej_tools = [
    ("TEJCompanyInfo", "tej.company_info"),
    ("TEJStockPrice", "tej.stock_price"),
    ("TEJMonthlyRevenue", "tej.monthly_revenue"),
    ("TEJInstitutionalHoldings", "tej.institutional_holdings"),
    ("TEJMarginTrading", "tej.margin_trading"),
    ("TEJForeignHoldings", "tej.foreign_holdings"),
    ("TEJFinancialSummary", "tej.financial_summary"),
    ("TEJFundNAV", "tej.fund_nav"),
    ("TEJShareholderMeeting", "tej.shareholder_meeting"),
    ("TEJFundBasicInfo", "tej.fund_basic_info"),
    ("TEJOffshoreFundInfo", "tej.offshore_fund_info"),
    ("TEJOffshoreFundDividend", "tej.offshore_fund_dividend"),
    ("TEJOffshoreFundHoldingsRegion", "tej.offshore_fund_holdings_region"),
    ("TEJOffshoreFundHoldingsIndustry", "tej.offshore_fund_holdings_industry"),
    ("TEJOffshoreFundNAVRank", "tej.offshore_fund_nav_rank"),
    ("TEJOffshoreFundNAVDaily", "tej.offshore_fund_nav_daily"),
    ("TEJOffshoreFundSuspension", "tej.offshore_fund_suspension"),
    ("TEJOffshoreFundPerformance", "tej.offshore_fund_performance"),
    ("TEJIFRSAccountDescriptions", "tej.ifrs_account_descriptions"),
    ("TEJFinancialCoverCumulative", "tej.financial_cover_cumulative"),
    ("TEJFinancialSummaryQuarterly", "tej.financial_summary_quarterly"),
    ("TEJFinancialCoverQuarterly", "tej.financial_cover_quarterly"),
    ("TEJFuturesData", "tej.futures_data"),
    ("TEJOptionsBasicInfo", "tej.options_basic_info"),
    ("TEJOptionsDailyTrading", "tej.options_daily_trading")
]

for class_name, tool_name in tej_tools:
    tool_registry.register_lazy(tool_name, lazy_import_factory("adapters.tej_adapter", class_name), group="financial_data", description="TEJ Financial Data")

# Internal Data Group
tool_registry.register_lazy("internal.search_company", lazy_import_factory("adapters.database_tool_adapter", "SearchCompany"), group="internal_data", description="Search Company")
tool_registry.register_lazy("internal.get_company_details", lazy_import_factory("adapters.database_tool_adapter", "GetCompanyDetails"), group="internal_data", description="Get Company Details")
tool_registry.register_lazy("internal.get_security_details", lazy_import_factory("adapters.database_tool_adapter", "GetSecurityDetails"), group="internal_data", description="Get Security Details")

# Internal Terms
tool_registry.register_lazy("internal.term_lookup", lazy_import_factory("adapters.internal_terms_adapter", "InternalTermLookup"), group="internal_data", description="Internal Term Lookup")
tool_registry.register_lazy("internal.term_explain", lazy_import_factory("adapters.internal_terms_adapter", "InternalTermExplain"), group="internal_data", description="Internal Term Explain")

# 在 worker 啟動時初始化資料庫與數據
# init_db()
#
# db = SessionLocal()
# try:
#     initialize_all(db)
# finally:
#     db.close()

def load_dynamic_tools():
    """Load dynamic tools from database. Should be called after DB init."""
    print("🔄 Loading Dynamic & OpenAPI tools from database...")
    
    # 1. Load User Defined Tools (HTTP/Python)
    # Note: These are dynamic, so we still load them eagerly or we could refactor to lazy too,
    # but for now we focus on the heavy static adapters.
    # To fix import errors, we need to import Adapters here since we removed top-level imports.
    from adapters.http_tool_adapter import HTTPToolAdapter
    from adapters.python_tool_adapter import PythonToolAdapter

    db = SessionLocal()
    try:
        custom_tools = db.query(models.Tool).filter(models.Tool.enabled == True).all()
        print(f"   Found {len(custom_tools)} custom tools in DB.")
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
                print(f"   ⚠️ Error registering custom tool {tool.name}: {e}")
    except Exception as e:
         print(f"   ⚠️ Error accessing database for custom tools: {e}")
    finally:
        db.close()

    # 2. Load OpenAPI Tools
    from worker.dynamic_tool_loader import DynamicToolLoader
    try:
        loaded_count = DynamicToolLoader.load_all_tools(tool_registry)
        print(f"   ✅ Successfully loaded {loaded_count} OpenAPI tools")
    except Exception as e:
        print(f"   ❌ Failed to load OpenAPI tools: {e}")
    print("✅ Dynamic tool loading complete.\n")

# Hook for Celery Worker Startup
from celery.signals import worker_process_init
@worker_process_init.connect
def on_worker_init(**kwargs):
    load_dynamic_tools()
