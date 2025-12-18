from agentscope.agent import AgentBase
from typing import Dict, Any, List, Optional
import re
import json
import asyncio
from worker.llm_utils import call_llm_async
from api.redis_client import get_redis_client
from api.tool_registry import tool_registry
from worker.tool_invoker import call_tool

class DataScientistAgent(AgentBase):
    """
    Open Data Scientist Agent
    
    A specialized agent that uses ReAct (Reasoning + Acting) to perform data analysis tasks.
    It generates and executes Python code in a sandboxed environment to answer queries.
    """
    
    def __init__(self, name: str, debate_id: str, **kwargs: Any):
        super().__init__()
        self.name = name
        self.debate_id = debate_id
        self.max_iterations = 5  # ReAct loop limit
        self.memory = []  # Stores the ReAct history

    def _publish_log(self, content: str):
        """Publish logs to Redis for real-time UI updates."""
        if not self.debate_id:
            return
            
        try:
            redis_client = get_redis_client()
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            ui_content = f"[{timestamp}] {content}"
            message = json.dumps({"role": f"DataScientist ({self.name})", "content": ui_content}, ensure_ascii=False)
            redis_client.publish(f"debate:{self.debate_id}:log_stream", message)
            redis_client.rpush(f"debate:{self.debate_id}:log_history", message)
        except Exception as e:
            print(f"DataScientist log error: {e}")

    async def reply(self, x: dict = None) -> dict:
        """
        Main entry point for the agent.
        x: {"content": "User query", "context": "Optional context"}
        """
        user_query = x.get("content", "")
        self._publish_log(f"📊 收到數據分析請求: {user_query}")
        
        # Initialize ReAct Context
        system_prompt = """
        You are an expert Data Scientist. You solve problems by writing and executing Python code.
        
        **Your Capabilities:**
        - You have access to a Python environment with pandas, numpy, matplotlib, seaborn, scikit-learn.
        - You can use the `python_repl` tool to execute code.
        - You can use `tej_tool` to fetch financial data.
        
        **ReAct Process:**
        1. **Thought**: Analyze the request and plan the next step.
        2. **Action**: Generate Python code to execute or call a tool.
        3. **Observation**: Read the execution result.
        4. **Repeat**: Continue until you have the answer.
        5. **Final Answer**: Summarize your findings with text and chart paths.
        
        **Rules:**
        - ALWAYS generate a plot if the data allows visualization.
        - Save plots to `./charts/` and return the path.
        - Do NOT hallucinate data. If you need data, write code to fetch it.
        - If you need external data, prefer using the `tej_tool` or `searxng`.
        """
        
        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        for i in range(self.max_iterations):
            self._publish_log(f"🔄 ReAct Iteration {i+1}/{self.max_iterations}")
            
            # 1. Thought & Action Generation
            response = await call_llm_async(
                messages=history,
                temperature=0.1, # Low temp for code generation
                context_tag=f"{self.debate_id}:ODS:ReAct:{i}"
            )
            
            # Append model response to history
            history.append({"role": "assistant", "content": response})
            
            # 2. Parse Action (Look for Python code blocks)
            # Pattern: ```python ... ```
            code_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
            
            if code_match:
                code = code_match.group(1)
                self._publish_log(f"💻 執行 Python 代碼:\n{code[:100]}...")
                
                # 3. Execute Code (via Tool Adapter)
                try:
                    # TODO: Switch to Docker Adapter later. Now using existing Python adapter.
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, call_tool, "python.execute", {"code": code})
                    
                    observation = f"Execution Result:\n{result}"
                    self._publish_log(f"✅ 執行成功 (Output len: {len(str(result))})")
                    
                except Exception as e:
                    observation = f"Execution Error: {str(e)}"
                    self._publish_log(f"❌ 執行錯誤: {str(e)}")
                
                # Append Observation
                history.append({"role": "user", "content": f"Observation: {observation}"})
                
            elif "Final Answer:" in response:
                self._publish_log("🏁 完成分析任務。")
                # Extract Final Answer
                final_answer = response.split("Final Answer:")[-1].strip()
                return {"content": final_answer, "type": "analysis_report"}
                
            else:
                # If no code and no final answer, treat as a thought step or ask LLM to continue
                # Sometimes LLM explains the plan but doesn't write code yet.
                # We can force it to act.
                if i == self.max_iterations - 1:
                    return {"content": "無法在限定步驟內完成分析。", "type": "error"}
                    
        return {"content": "ReAct loop limit reached.", "type": "error"}
