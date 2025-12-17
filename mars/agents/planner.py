import json
from typing import List
from mars.types.artifact import ResearchPlan, Task
from worker.llm_utils import call_llm_async

class PlannerAgent:
    """
    MARS Planner Agent
    Responsible for decomposing the user query into a structured Research Plan (DAG).
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name

    async def generate_plan(self, topic: str) -> ResearchPlan:
        """
        Generate a ResearchPlan for the given topic.
        """
        system_prompt = """
你是 MARS (Multi-Agent Research System) 的研究規劃師。
你的目標是將複雜的研究主題拆解為數個具體、可執行的小任務 (Tasks)。
這些任務應形成合理的依賴關係 (DAG)。

【輸出格式】 (JSON Only):
{
  "goal": "研究目標",
  "tasks": [
    {
      "id": "任務ID (例如 T1, T2)",
      "description": "具體執行的動作。⚠️ 重要：若主題包含股票代號 (如 2480.TW)，請務必在每個相關任務描述中明確保留該代號，以便工具調用。",
      "assigned_role": "角色名稱",
      "dependencies": ["依賴的任務ID"] (可選)
    }
  ]
}

【可用角色】
- Industry Researcher (產業研究員): 查詢市場趨勢、新聞、競爭對手 (擅長 Search, Company Info)。
- Quantitative Analyst (量化分析師): 分析財報、股價、籌碼數據 (擅長 TEJ Stock/Financial)。
- Risk Officer (風控官): 查詢融資券、外資動向、風險指標。
- Valuation Expert (估值專家): 查詢股利政策、本益比、IFRS 數據。

請使用繁體中文描述任務。
"""
        user_prompt = f"Topic: {topic}\nPlease generate a comprehensive research plan."

        try:
            # Force bypass cache for debugging if needed, or just log
            response = await call_llm_async(user_prompt, system_prompt=system_prompt, model=self.model_name)
            print(f"[Planner] Raw LLM Response: {response}")
            
            # Parse JSON
            # Basic cleanup if markdown blocks are used
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            data = json.loads(clean_response)
            
            tasks = []
            for t in data.get("tasks", []):
                tasks.append(Task(
                    id=t["id"],
                    description=t["description"],
                    assigned_role=t["assigned_role"],
                    dependencies=t.get("dependencies", [])
                ))
            
            return ResearchPlan(
                id=f"plan_{int(json.dumps(data).__hash__())}", # Simple unique ID
                content=data.get("goal", topic),
                source_agent="Planner",
                tasks=tasks
            )

        except Exception as e:
            print(f"Planner failed: {e}")
            # Return a fallback plan
            return ResearchPlan(
                id="fallback_plan",
                content=f"Research on {topic} (Fallback)",
                source_agent="System",
                tasks=[
                    Task(id="task_1", description=f"Analyze {topic}", assigned_role="Industry Researcher")
                ]
            )