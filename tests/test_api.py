import pytest
import requests
import json
import time
from typing import Dict, Any

# API 的基本 URL
BASE_URL = "http://api:8000/api/v1"

# 預設的工具設定，用於測試
DEFAULT_TOOL_CONFIG = {
    "name": "test_tool",
    "description": "A tool for testing purposes.",
    "config": {
        "provider": "openai",
        "model": "gpt-4",
    }
}

@pytest.fixture(scope="session", autouse=True)
def wait_for_api():
    """
    在所有測試開始前，等待 API 服務啟動。
    """
    start_time = time.time()
    while time.time() - start_time < 30:  # 最多等待 30 秒
        try:
            response = requests.get(f"{BASE_URL}/tools")
            if response.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    pytest.fail("API service did not start within 30 seconds.")

@pytest.fixture(autouse=True)
def clear_custom_tools():
    """
    在每次測試前，清除所有由測試案例新增的自訂工具。
    """
    response = requests.get(f"{BASE_URL}/tools")
    tools = response.json()
    for tool_name in tools.keys():
        if tool_name != "searxng.search":
            requests.delete(f"{BASE_URL}/tools/{tool_name}")

def test_list_tools_contains_default_tool():
    """
    測試工具列表中，應包含預設的 searxng.search 工具。
    """
    response = requests.get(f"{BASE_URL}/tools")
    assert response.status_code == 200
    tools = response.json()
    assert "searxng.search" in tools

def test_test_tool():
    """
    測試工具测试端點。
    """
    test_data = {
        "name": "searxng.search",
        "kwargs": {
            "q": "test query"
        }
    }
    response = requests.post(f"{BASE_URL}/tools/test", json=test_data)
    assert response.status_code == 200
    result = response.json()
    assert result["tool"] == "searxng.search"
    assert "result" in result
    # 這裡我們假設 SearXNG 搜尋會返回一個包含 "data" 的字典
    assert "data" in result["result"]

