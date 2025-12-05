from worker.celery_app import app
from worker.tool_invoker import call_tool
from worker.chairman import Chairman
from worker.debate_cycle import DebateCycle
from typing import Dict, Any, List
from agentscope.agent import AgentBase
import redis
import json
import os

@app.task
def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    執行指定的工具。
    """
    return call_tool(tool_name, params)

from api.database import SessionLocal
from api import models

@app.task(bind=True)
def run_debate_cycle(self, topic: str, pro_team_configs: List[Dict], con_team_configs: List[Dict], rounds: int):
    """
    執行辯論循環並將結果存檔。
    """
    debate_id = self.request.id
    chairman = Chairman(name="主席")
    
    # 如果沒有提供正方隊伍配置，創建預設 Agent
    pro_team = []
    if not pro_team_configs or len(pro_team_configs) == 0:
        # 創建預設的正方 Agent
        for i in range(2):  # 預設 2 個 Agent
            agent = AgentBase()
            agent.name = f"正方辯士 {i+1}"
            pro_team.append(agent)
    else:
        for c in pro_team_configs:
            agent = AgentBase()
            # 處理字串或字典類型
            if isinstance(c, dict):
                agent.name = c.get('name', f"正方辯士")
            elif isinstance(c, str):
                agent.name = f"正方辯士 ({c[:8]})"  # 使用 ID 的前 8 個字符
            else:
                agent.name = "正方辯士"
            pro_team.append(agent)
    
    # 如果沒有提供反方隊伍配置，創建預設 Agent
    con_team = []
    if not con_team_configs or len(con_team_configs) == 0:
        # 創建預設的反方 Agent
        for i in range(2):  # 預設 2 個 Agent
            agent = AgentBase()
            agent.name = f"反方辯士 {i+1}"
            con_team.append(agent)
    else:
        for c in con_team_configs:
            agent = AgentBase()
            # 處理字串或字典類型
            if isinstance(c, dict):
                agent.name = c.get('name', f"反方辯士")
            elif isinstance(c, str):
                agent.name = f"反方辯士 ({c[:8]})"  # 使用 ID 的前 8 個字符
            else:
                agent.name = "反方辯士"
            con_team.append(agent)

    debate = DebateCycle(debate_id, topic, chairman, pro_team, con_team, rounds)
    debate_result = debate.start()

    db = SessionLocal()
    try:
        archive = models.DebateArchive(
            topic=debate_result["topic"],
            analysis_json=debate_result.get("analysis", {}),
            rounds_json=debate_result["rounds_data"],
            logs_json={}
        )
        db.add(archive)
        db.commit()
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=5, max_retries=3)
    finally:
        db.close()
    
    return debate_result

def _select_agent(team: List[AgentBase], round_num: int) -> AgentBase:
    """
    从队伍中选择一个智能体发言。
    """
    return team[(round_num - 1) % len(team)]
