import agentscope
from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.tool import Toolkit, ToolResponse
from agentscope.model import OllamaChatModel
from agentscope.formatter import OllamaChatFormatter
from agentscope.memory import InMemoryMemory
from adapters.searxng_adapter import SearXNGAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.yfinance_adapter import YFinanceAdapter
import os
import json
import asyncio

# 1. 準備工具函數
searxng_adapter = SearXNGAdapter()
ddg_adapter = DuckDuckGoAdapter()
yf_adapter = YFinanceAdapter()

def search_with_searxng(q: str, category: str = "general", limit: int = 5):
    """
    Use SearXNG search engine to search for information.
    
    Args:
        q (str): The search keyword.
        category (str): The search category, default is "general".
        limit (int): The number of results to return, default is 5.
    """
    print(f"[System] Invoking SearXNG with q='{q}'")
    result = searxng_adapter.invoke(q=q, category=category, limit=limit)
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(result, ensure_ascii=False))]
    )

def search_with_duckduckgo(q: str, max_results: int = 5):
    """
    Use DuckDuckGo search engine to search for information.
    
    Args:
        q (str): The search keyword.
        max_results (int): The number of results to return, default is 5.
    """
    print(f"[System] Invoking DuckDuckGo with q='{q}'")
    result = ddg_adapter.invoke(q=q, max_results=max_results)
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(result, ensure_ascii=False))]
    )

def get_stock_info(symbol: str, info_type: str = "basic"):
    """
    Get stock information using yfinance.
    
    Args:
        symbol (str): Stock symbol (e.g., AAPL, TSLA).
        info_type (str): Type of information (basic, history, news). Default is "basic".
    """
    print(f"[System] Invoking YFinance with symbol='{symbol}', info_type='{info_type}'")
    result = yf_adapter.invoke(symbol=symbol, info_type=info_type)
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(result, ensure_ascii=False))]
    )

# 2. 初始化模型
model_name = os.environ.get("OLLAMA_MODEL", "llama3")
host = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")

print(f"Initializing Ollama model: {model_name} at {host}")

try:
    model = OllamaChatModel(
        model_name=model_name,
        host=host,
    )
except ImportError:
    print("Error: 'ollama' package not found. Please install it.")
    exit(1)

# 3. 準備工具箱
toolkit = Toolkit()
toolkit.register_tool_function(search_with_searxng)
toolkit.register_tool_function(search_with_duckduckgo)
toolkit.register_tool_function(get_stock_info)

# 4. 創建 Agent
agent = ReActAgent(
    name="Tester",
    sys_prompt="You are a helpful assistant. When asked to search or get stock info, use the appropriate tool. Always confirm which tool you used in your response.",
    model=model,
    formatter=OllamaChatFormatter(),
    toolkit=toolkit,
    memory=InMemoryMemory(),
)

# 5. 執行測試
async def run_test():
    print("\n=== Test 1: SearXNG ===")
    msg1 = Msg(name="User", content="Please use SearXNG to search for 'AgentScope framework'.", role="user")
    try:
        response1 = await agent(msg1)
        print(f"Agent Response: {response1.content}")
    except Exception as e:
        print(f"Test 1 failed: {e}")

    print("\n=== Test 2: DuckDuckGo ===")
    msg2 = Msg(name="User", content="Please use DuckDuckGo to search for 'Python programming'.", role="user")
    try:
        response2 = await agent(msg2)
        print(f"Agent Response: {response2.content}")
    except Exception as e:
        print(f"Test 2 failed: {e}")

    print("\n=== Test 3: YFinance ===")
    msg3 = Msg(name="User", content="What is the current price of Apple (AAPL)?", role="user")
    try:
        response3 = await agent(msg3)
        print(f"Agent Response: {response3.content}")
    except Exception as e:
        print(f"Test 3 failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
