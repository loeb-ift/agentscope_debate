from worker.tasks import run_debate_cycle

def test_run_debate_cycle_task():
    """
    測試 `run_debate_cycle` Celery 任務是否可以成功同步執行。
    """
    pro_team = [{"name": "Agent1"}, {"name": "Agent2"}]
    con_team = [{"name": "Agent3"}, {"name": "Agent4"}]
    rounds = 2
    topic = "Test Topic"

    # 直接調用任務函數
    debate_result = run_debate_cycle(topic, pro_team, con_team, rounds)


    # 驗證返回值
    assert isinstance(debate_result, dict)
    assert debate_result["topic"] == topic
    assert len(debate_result["rounds_data"]) == rounds
