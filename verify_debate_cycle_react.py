import asyncio
import json
import logging
import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Any

# Add current directory to path
sys.path.append(os.getcwd())

from worker.llm_utils import call_llm
from api.tool_registry import tool_registry
from worker.dynamic_tool_loader import DynamicToolLoader, OpenAPIToolAdapter

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ReActSimulator")

def ensure_chinatimes_tool():
    """Ensure ChinaTimes tool is registered for testing"""
    tool_name = "news.search_chinatimes"
    tools = tool_registry.list_tools()
    
    if any(k.startswith(tool_name) for k in tools.keys()):
        logger.info(f"✅ 工具 {tool_name} 已存在於 Registry。")
        return

    logger.info(f"⚠️ 工具 {tool_name} 未找到，正在進行手動註冊...")
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {
            "/search/content": {
                "get": {
                    "summary": "搜尋中時新聞網",
                    "description": "根據關鍵字搜尋相關新聞",
                    "operationId": "search_news",
                    "parameters": [
                        {
                            "name": "Keyword",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "搜尋關鍵字 (例如: 公司名稱, 議題)"
                        }
                    ]
                }
            }
        }
    }

    adapter = OpenAPIToolAdapter({
        'name': tool_name,
        'version': 'v1',
        'description': '搜尋中時新聞網 (ChinaTimes) 的最新新聞報導',
        'openapi_spec': openapi_spec,
        'base_url': 'https://es.chinatimes.com',
        'auth_type': 'none',
        'provider': 'chinatimes',
        'timeout': 15
    })

    tool_registry.register(adapter, group="news")
    logger.info(f"✅ {tool_name} 手動註冊完成。")

class MockAgent:
    def __init__(self, name):
        self.name = name
        self.system_prompt = ""

class ReActSimulator:
    def __init__(self):
        self.debate_id = "sim_react_001"
        self.topic = "分析中光電(5371)的近期市場動態與擴廠計畫"
        self.agent_tools_map = {}
        self.debug_trace = []
        self.tool_stats = {"count": 0, "total_time": 0.0}
        
    def _publish_log(self, role, content):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{role}]: {str(content)[:200]}...")

    async def call_llm_async_sim(self, prompt, system_prompt, context_tag, tools=None):
        """Wrapper to call sync call_llm in executor"""
        loop = asyncio.get_running_loop()
        logger.info(f"🤖 Calling LLM (Tag: {context_tag})...")
        
        # Use verify_debate_tool_usage.py style call
        return await loop.run_in_executor(
            None, 
            lambda: call_llm(prompt=prompt, system_prompt=system_prompt, tools=tools)
        )

    async def _agent_turn_async(self, agent: MockAgent, side: str, round_num: int) -> str:
        """
        Simulated _agent_turn_async from worker/debate_cycle.py
        """
        print(f"\n=== Agent {agent.name} ({side}) Turn Starts ===")
        self._publish_log(f"{agent.name} (Thinking)", "正在思考並決定使用的策略...")
        
        # 1. 構建 Tool Definitions (Ollama Format)
        selected_tool_names = self.agent_tools_map.get(agent.name, [])
        ollama_tools = []
        filtered_tools = {}

        if selected_tool_names:
            for name in selected_tool_names:
                try:
                    tool_data = tool_registry.get_tool_data(name)
                    filtered_tools[name] = tool_data
                    
                    params_schema = tool_data.get('schema', {"type": "object", "properties": {}})
                    desc = tool_data.get('description', '')
                    if isinstance(desc, dict): desc = desc.get('description', '')

                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": desc,
                            "parameters": params_schema
                        }
                    })
                except Exception as e:
                    logger.warning(f"Tool setup error for {name}: {e}")

            tools_desc = "你已選擇並激活以下工具：\n" + "\n".join([f"- {name}: {data['description']}" for name, data in filtered_tools.items()])
        else:
            tools_desc = "No tools selected."

        # 2. Construct Prompts (Simulated PromptService)
        system_prompt = f"""
你是 {agent.name}，代表 {side} 方。
辯題：{self.topic}
立場：{side}

# Operational Rules
System Rules: Use tools first to gather evidence. Do NOT fabricate data.
If you have enough information, output your final argument as text.
"""
        
        user_prompt = f"""
Current Round: {round_num}
Instructions: 
1. Analyze the topic: "{self.topic}"
2. Use available tools to gather data if needed.
3. Available Tools: 
{tools_desc}

請開始分析。
"""

        # 3. ReAct Loop
        max_steps = 3
        current_step = 0
        current_prompt = user_prompt
        collected_evidence = []
        
        while current_step < max_steps:
            current_step += 1
            print(f"\n--- Step {current_step}/{max_steps} ---")
            
            # Call LLM
            response = await self.call_llm_async_sim(
                current_prompt,
                system_prompt=system_prompt,
                context_tag=f"{self.debate_id}:{agent.name}",
                tools=ollama_tools if ollama_tools else None
            )
            
            print(f"LLM Response (Raw Preview): {response[:200]}")

            # Check for tool call
            is_tool_call = False
            tool_call_data = None
            
            try:
                # 嘗試提取 JSON
                # 簡單正則提取第一個 JSON 對象
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    possible_json = json_match.group(0)
                    try:
                        parsed = json.loads(possible_json)
                        if "tool" in parsed and "params" in parsed:
                            tool_call_data = parsed
                            is_tool_call = True
                    except:
                        pass
            except Exception as e:
                logger.error(f"JSON Parsing Error: {e}")

            if not is_tool_call:
                # No tool call -> Assume final speech
                self._publish_log(f"{agent.name} (Speech)", f"Final Response: {response}")
                return response

            # Execute Tool
            tool_name = tool_call_data["tool"]
            params = tool_call_data["params"]
            
            self._publish_log(f"{agent.name} (Tool)", f"Calling {tool_name} with {params}")
            
            try:
                # Direct invocation (Bypassing Hippocampus/Redis for simulation)
                tool_instance = tool_registry.get_tool_data(tool_name)["instance"]
                
                start_time = datetime.now()
                # Run sync tool in executor to mimic async behavior
                loop = asyncio.get_running_loop()
                tool_result = await loop.run_in_executor(None, lambda: tool_instance.invoke(**params))
                duration = (datetime.now() - start_time).total_seconds()
                
                # Format result
                result_str = json.dumps(tool_result, ensure_ascii=False)
                if len(result_str) > 500:
                    result_preview = result_str[:500] + "... (truncated)"
                else:
                    result_preview = result_str
                
                self._publish_log(f"{agent.name} (Result)", f"Result: {result_preview}")
                
                # Append to evidence
                collected_evidence.append(f"【Tool: {tool_name}】\nParams: {params}\nResult: {result_preview}")
                
                # Update Prompt for next step
                current_prompt = f"""
Tool '{tool_name}' execution result:
{result_str}

【系統提示】
1. 請檢查上述結果。
2. 如果證據已足夠支持你的論點，請輸出最終發言（純文字）。
3. 如果需要更多資訊，請繼續調用工具。
"""
                
            except Exception as e:
                error_msg = f"Tool execution error: {str(e)}"
                logger.error(error_msg)
                current_prompt = f"系統錯誤：{error_msg}\n請重新選擇有效的工具或發表言論。"

        # Force Conclusion if loop ends
        print("Max steps reached. Forcing conclusion.")
        evidence_text = "\n".join(collected_evidence)
        final_prompt = f"""
【系統強制指令】
你已經達到工具調用次數上限。
請根據你目前已蒐集到的證據，立即發表你的本輪論點。

**已蒐集的證據**：
{evidence_text}

請直接輸出你的辯論發言（純文字）：
"""
        final_response = await self.call_llm_async_sim(
            final_prompt,
            system_prompt=system_prompt,
            context_tag=f"{self.debate_id}:{agent.name}:Force",
            tools=None
        )
        self._publish_log(f"{agent.name} (ForceSpeech)", final_response)
        return final_response

async def main():
    print("🚀 Starting ReAct Simulation...")
    
    # 1. Setup Environment
    sim = ReActSimulator()
    ensure_chinatimes_tool()
    
    # 2. Setup Agent
    agent = MockAgent("Analyst_Wang")
    
    # Assign the new tool to the agent
    sim.agent_tools_map[agent.name] = ["news.search_chinatimes"]
    
    # 3. Run Turn
    print(f"\nTopic: {sim.topic}")
    print(f"Agent: {agent.name}")
    print(f"Tools: {sim.agent_tools_map[agent.name]}")
    
    final_output = await sim._agent_turn_async(agent, "pro", 1)
    
    print("\n=== Simulation Complete ===")
    print("Final Output Length:", len(final_output))

if __name__ == "__main__":
    asyncio.run(main())