from adapters.tej_adapter import TEJOffshoreFundInfo, TEJOptionsBasicInfo
from adapters.searxng_adapter import SearXNGAdapter
from adapters.internal_terms_adapter import InternalTermLookup
from adapters.chinatimes_adapter import ChinaTimesAdapter
from adapters.google_cse_adapter import GoogleCSEAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.yfinance_adapter import YFinanceAdapter
from adapters.memory_adapter import SearchSharedMemory
from adapters.database_tool_adapter import SearchCompany
from adapters.chinatimes_suite import ChinaTimesStockRTAdapter

def print_tool_info(tool_cls):
    tool = tool_cls()
    print(f"--- {tool.name} ---")
    print(f"Description: {tool.description}")
    print("-" * 30)

if __name__ == "__main__":
    print("Verifying Tool Descriptions...\n")
    print_tool_info(TEJOffshoreFundInfo)
    print_tool_info(SearXNGAdapter)
    print_tool_info(InternalTermLookup)
    print_tool_info(ChinaTimesAdapter)
    print_tool_info(GoogleCSEAdapter)
    print_tool_info(DuckDuckGoAdapter)
    print_tool_info(YFinanceAdapter)
    print_tool_info(SearchSharedMemory)
    print_tool_info(SearchCompany)
    print_tool_info(ChinaTimesStockRTAdapter)