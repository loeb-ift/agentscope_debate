from typing import List, Dict, Any
from worker.chairman import Chairman
from agentscope.agent import AgentBase
import redis
import json
from worker import tasks
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE

class DebateCycle:
    """
    管理整个辩论循环，包括主席引导、正反方发言和总结。
    """

    def __init__(self, debate_id: str, topic: str, chairman: Chairman, pro_team: List[AgentBase], con_team: List[AgentBase], rounds: int):
        self.debate_id = debate_id
        self.topic = topic
        self.chairman = chairman
        self.pro_team = pro_team
        self.con_team = con_team
        self.rounds = rounds
        self.redis_client = redis.Redis(host='redis', port=6379, db=0)
        self.evidence_key = f"debate:{self.debate_id}:evidence"
        self.rounds_data = []
        self.analysis_result = {}
        self.history = []

    def _publish_log(self, role: str, content: str):
        """
        發布日誌到 Redis，供前端 SSE 訂閱。
        """
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", message)

    def start(self) -> Dict[str, Any]:
        """
        开始辩论循环。
        """
        print(f"Debate '{self.debate_id}' has started.")
        self._publish_log("System", f"Debate '{self.debate_id}' has started.")
        
        # 0. 賽前分析
        self.analysis_result = self.chairman.pre_debate_analysis(self.topic)
        summary = self.analysis_result.get('step5_summary', '無')
        self.chairman.speak(f"賽前分析完成。戰略摘要：{summary}")
        self._publish_log("Chairman (Analysis)", f"賽前分析完成。\n戰略摘要：{summary}")
        
        for i in range(1, self.rounds + 1):
            print(f"--- Round {i} ---")
            self._publish_log("System", f"--- Round {i} ---")
            round_result = self._run_round(i)
            self.rounds_data.append(round_result)
        
        print(f"Debate '{self.debate_id}' has ended.")
        self._publish_log("System", f"Debate '{self.debate_id}' has ended.")
        return {"topic": self.topic, "rounds_data": self.rounds_data, "analysis": self.analysis_result}

    def _run_round(self, round_num: int) -> Dict[str, Any]:
        """
        运行一轮辩论 (同步执行)。
        """
        # 1. 主席引导
        opening = f"现在开始第 {round_num} 轮辩论。"
        self.chairman.speak(opening)
        self.history.append({"role": "Chairman", "content": opening})
        self._publish_log("Chairman", opening)

        # 2. 正反方发言
        pro_agent = tasks._select_agent(self.pro_team, round_num)
        pro_content = self._agent_turn(pro_agent, "正方", round_num)
        self.history.append({"role": f"Pro ({pro_agent.name})", "content": pro_content})
        self._publish_log(f"Pro ({pro_agent.name})", pro_content)
        
        con_agent = tasks._select_agent(self.con_team, round_num)
        con_content = self._agent_turn(con_agent, "反方", round_num)
        self.history.append({"role": f"Con ({con_agent.name})", "content": con_content})
        self._publish_log(f"Con ({con_agent.name})", con_content)

        # 3. 主席总结
        self.chairman.summarize_round(self.debate_id, round_num)
        self._publish_log("Chairman", f"Round {round_num} summary completed.")
        
        return {
            "round": round_num,
            "pro_agent": pro_agent.name,
            "pro_content": pro_content,
            "con_agent": con_agent.name,
            "con_content": con_content,
            "summary": f"Round {round_num} completed."
        }

    def _agent_turn(self, agent: AgentBase, side: str, round_num: int) -> str:
        """
        執行單個 Agent 的回合：思考 -> 工具 -> 發言
        """
        print(f"Agent {agent.name} ({side}) is thinking...")
        
        # 構建 Prompt - 強烈鼓勵使用工具
        tools_desc = get_tools_description()
        tools_examples = get_tools_examples()
        
        system_prompt = f"""你是 {agent.name}，代表{side}。
辯題：{self.topic}

**重要指示**：
1. 你必須先使用工具獲取真實數據，再發表論點
2. 對於台股相關問題，必須使用 TEJ 工具
3. 工具調用格式必須是純 JSON，不要有其他文字
4. 調用工具後，你會收到數據，然後基於數據發言
"""
        
        user_prompt = f"""
這是第 {round_num} 輪辯論。主席戰略摘要：{self.analysis_result.get('step5_summary', '無')}

**背景資訊**：
- 當前日期：{CURRENT_DATE}
- 辯題涉及：2024 年 Q4（2024-10-01 至 2024-12-31）
- 你需要查詢 2024 年的實際股價數據進行比較

**重要常數**：
{chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()])}

**第一步：必須先調用工具獲取數據**

{tools_desc}

{tools_examples}

**請現在就調用工具**（只輸出 JSON，不要其他文字）：
"""
        
        response = call_llm(user_prompt, system_prompt=system_prompt)
        print(f"DEBUG: Agent {agent.name} raw response: {response[:500]}")  # 只印前 500 字符

        # Retry 機制
        if not response:
            print(f"WARNING: Empty response from {agent.name}, retrying with simple prompt...")
            retry_prompt = f"請針對辯題「{self.topic}」發表你的{side}論點。請務必使用繁體中文。"
            response = call_llm(retry_prompt, system_prompt=system_prompt)
            print(f"DEBUG: Agent {agent.name} retry response: {response[:500]}")
        
        # 檢查是否調用工具
        print(f"DEBUG: Checking for tool call in response (length: {len(response)})")
        
        try:
            if "{" in response and "}" in response:
                # 嘗試提取 JSON
                json_str = response[response.find("{"):response.rfind("}")+1]
                print(f"DEBUG: Extracted JSON string: {json_str[:200]}...")
                
                try:
                    tool_call = json.loads(json_str)
                    print(f"DEBUG: Successfully parsed JSON: {tool_call}")
                except json.JSONDecodeError as e:
                    print(f"WARNING: JSON decode failed: {e}")
                    print(f"DEBUG: Failed JSON string: {json_str}")
                    return response

                if "tool" in tool_call and "params" in tool_call:
                    tool_name = tool_call["tool"]
                    params = tool_call["params"]
                    
                    print(f"✓ Agent {agent.name} is calling tool: {tool_name}")
                    print(f"✓ Tool parameters: {json.dumps(params, ensure_ascii=False)}")
                    self._publish_log(f"{agent.name} (Tool)", f"Calling {tool_name} with {params}")
                    
                    # 執行工具 (支援所有註冊的工具)
                    try:
                        print(f"DEBUG: Executing tool {tool_name}...")
                        tool_result = tasks.execute_tool(tool_name, params)
                        print(f"✓ Tool execution successful")
                        print(f"DEBUG: Tool result preview: {str(tool_result)[:300]}...")
                    except Exception as e:
                        tool_result = {"error": f"Tool execution error: {str(e)}"}
                        print(f"ERROR: Tool {tool_name} execution failed: {e}")
                    
                    # 將工具結果反饋給 Agent 生成最終發言
                    prompt_with_tool = f"""工具 {tool_name} 的執行結果：

{json.dumps(tool_result, ensure_ascii=False, indent=2)}

請根據這些證據進行發言。請務必使用繁體中文，並引用具體數據。"""
                    
                    print(f"DEBUG: Asking agent to generate final response based on tool result...")
                    final_response = call_llm(prompt_with_tool, system_prompt=system_prompt)
                    print(f"DEBUG: Agent {agent.name} final response: {final_response[:500]}...")
                    return final_response
                else:
                    print(f"DEBUG: JSON parsed but missing 'tool' or 'params' keys: {tool_call.keys()}")
            else:
                print(f"DEBUG: No JSON structure found in response")
        except Exception as e:
            print(f"ERROR: Tool execution parsing failed: {e}")
            import traceback
            traceback.print_exc()
        
        return response


