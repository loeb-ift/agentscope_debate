import pytest
import requests
import time
import json

BASE_URL = "http://localhost:8000/api/v1"

@pytest.fixture(scope="session", autouse=True)
def wait_for_api():
    """
    等待 API 服務啟動。
    """
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            response = requests.get("http://localhost:8000/tools")
            if response.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    pytest.fail("API service did not start within 60 seconds.")

def test_full_debate_flow():
    """
    測試完整的端到端辯論流程。
    """
    # 1. 創建辯論
    debate_config = {
        "topic": "Should AI be regulated?",
        "config": {
            "pro_team": [{"name": "AI-Pro-1"}, {"name": "AI-Pro-2"}],
            "con_team": [{"name": "AI-Con-1"}, {"name": "AI-Con-2"}],
            "rounds": 2
        }
    }
    response = requests.post(f"{BASE_URL}/debates", json=debate_config)
    assert response.status_code == 201
    task_info = response.json()
    task_id = task_info["task_id"]
    assert task_id

    # 2. 輪詢辯論狀態直到完成
    start_time = time.time()
    while time.time() - start_time < 120: # 2分鐘超時
        status_response = requests.get(f"{BASE_URL}/debates/{task_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        if status_data["status"] == "SUCCESS":
            break
        elif status_data["status"] == "FAILURE":
            pytest.fail(f"Debate task failed. Status data: {status_data}")
        time.sleep(5)
    else:
        pytest.fail("Debate did not complete within 120 seconds.")

    # 3. (可選) 驗證存檔的辯論
    archive_response = requests.get(f"{BASE_URL}/debates")
    assert archive_response.status_code == 200
    archives = archive_response.json()
    assert any(d["topic"] == debate_config["topic"] for d in archives)
