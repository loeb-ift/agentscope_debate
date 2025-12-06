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
def run_debate_cycle(self, topic: str, teams_config: List[Dict], rounds: int):
    """
    執行辯論循環並將結果存檔。
    teams_config format: [{"name": "Team A", "side": "pro", "agents": [...]}, ...]
    """
    debate_id = self.request.id
    chairman = Chairman(name="主席")
    
    debate_teams = []
    for t_config in teams_config:
        team_agents = []
        agent_configs = t_config.get("agents", [])
        
        if not agent_configs:
            # Default fallback (should happen rarely if validated upstream)
             for i in range(2):
                agent = AgentBase()
                agent.name = f"{t_config.get('name', '辯士')} {i+1}"
                team_agents.append(agent)
        else:
            for c in agent_configs:
                agent = AgentBase()
                if isinstance(c, dict):
                    agent.name = c.get('name', '辯士')
                else:
                    agent.name = "辯士"
                team_agents.append(agent)
        
        debate_teams.append({
            "name": t_config.get("name"),
            "side": t_config.get("side"),
            "agents": team_agents
        })
    
    # Fallback for legacy calls (if any) or empty teams
    if not debate_teams:
        # Create default pro/con
        pass

    debate = DebateCycle(debate_id, topic, chairman, debate_teams, rounds)
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
