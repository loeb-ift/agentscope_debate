from typing import List, Dict, Any
from worker.chairman import Chairman
from agentscope.agent import AgentBase
import redis
import json
import re
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from worker.memory import ReMePersonalLongTermMemory, ReMeTaskLongTermMemory, ReMeToolLongTermMemory
from api.tool_registry import tool_registry
from api.toolset_service import ToolSetService

class DebateCycle:
    """
    管理整个辩论循环，包括主席引导、正反方发言和总结。
    """

    def __init__(self, debate_id: str, topic: str, chairman: Chairman, teams: List[Dict], rounds: int):
        self.debate_id = debate_id
        self.topic = topic
        self.chairman = chairman
        self.teams = teams # List of dicts: [{"name": "...", "side": "...", "agents": [AgentBase...]}]
        self.rounds = rounds
        self.redis_client = redis.Redis(host='redis', port=6379, db=0)
        self.evidence_key = f"debate:{self.debate_id}:evidence"
        self.rounds_data = []
        self.analysis_result = {}
        self.history = []
        self.compressed_history = "無"  # 存儲 LLM 壓縮後的歷史摘要
        self.agent_tools_map = {} # 存儲每個 Agent 選擇的工具列表

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
        # Check Task LTM for similar past debates
        with ReMeTaskLongTermMemory() as task_mem:
            similar_tasks = task_mem.retrieve_similar_tasks(self.topic)
            if similar_tasks:
                print(f"DEBUG: Found similar past debates:\n{similar_tasks}")
                self._publish_log("System", f"Found similar past debates:\n{similar_tasks}")

        self.analysis_result = self.chairman.pre_debate_analysis(self.topic)
        summary = self.analysis_result.get('step5_summary', '無')
        self.chairman.speak(f"賽前分析完成。戰略摘要：{summary}")
        self._publish_log("Chairman (Analysis)", f"賽前分析完成。\n戰略摘要：{summary}")
        
        # 1. Agent 動態選擇工具 (Initialization Phase)
        print("Agents are selecting their tools...")
        for team in self.teams:
            side = team.get('side', 'neutral')
            for agent in team['agents']:
                self._agent_select_tools(agent, side)
        
        for i in range(1, self.rounds + 1):
            print(f"--- Round {i} ---")
            self._publish_log("System", f"--- Round {i} ---")
            round_result = self._run_round(i)
            self.rounds_data.append(round_result)
        
        # 4. 最終總結
        handcard = self.analysis_result.get('step6_handcard') or self.analysis_result.get('step5_summary', '無手卡')
        final_conclusion = self.chairman.summarize_debate(self.debate_id, self.topic, self.rounds_data, handcard)
        self._publish_log("Chairman (Conclusion)", final_conclusion)

        # Record outcome to Task LTM
        with ReMeTaskLongTermMemory() as task_mem:
            task_mem.record(self.topic, final_conclusion)

        print(f"Debate '{self.debate_id}' has ended.")
        self._publish_log("System", f"Debate '{self.debate_id}' has ended.")
        
        return {
            "topic": self.topic,
            "rounds_data": self.rounds_data,
            "analysis": self.analysis_result,
            "final_conclusion": final_conclusion
        }

    def _run_round(self, round_num: int) -> Dict[str, Any]:
        """
        运行一轮辩论 (同步执行)。
        包含：各團隊內部討論 -> 團隊總結 -> 主席彙整與下一輪引導
        """
        from worker import tasks # Lazy import to avoid circular dependency
        
        # 1. 主席引导
        opening = f"现在開始第 {round_num} 輪辯論。"
        self.chairman.speak(opening)
        self.history.append({"role": "Chairman", "content": opening})
        self._publish_log("Chairman", opening)

        # 2. 各團隊內部辯論與總結 (Intra-Team Debate & Summary)
        round_team_summaries = {}
        
        for team in self.teams:
            team_name = team['name']
            team_side = team.get('side', 'neutral')
            team_agents = team['agents']
            
            print(f"--- Team {team_name} is deliberating ---")
            self._publish_log("System", f"--- Team {team_name} 正在進行內部討論 ---")
            
            team_discussion_log = []
            
            # 每個 Agent 輪流發言 (模擬內部討論)
            for agent in team_agents:
                content = self._agent_turn(agent, team_name, round_num)
                role_label = f"{team_name} - {agent.name}"
                self.history.append({"role": role_label, "content": content})
                self._publish_log(role_label, content)
                team_discussion_log.append(f"{agent.name}: {content}")
            
            # 生成團隊共識與分歧總結
            team_summary = self._generate_team_summary(team_name, team_discussion_log)
            self._publish_log(f"{team_name} (Summary)", team_summary)
            round_team_summaries[team_name] = team_summary
            self.history.append({"role": f"{team_name} Summary", "content": team_summary})
            
        # 3. 主席彙整與下一輪方向
        handcard = self.analysis_result.get('step6_handcard') or self.analysis_result.get('step5_summary', '無手卡')
        
        # 臨時方案：將 team_summaries 寫入 Redis evidence，讓主席讀取到
        for t_name, t_summary in round_team_summaries.items():
            summary_evidence = {
                "role": f"{t_name} Summary",
                "content": t_summary,
                "type": "team_summary"
            }
            self.redis_client.rpush(self.evidence_key, json.dumps(summary_evidence, ensure_ascii=False))
            
        next_direction = self.chairman.summarize_round(self.debate_id, round_num, handcard=handcard)
        self._publish_log("Chairman", f"Round {round_num} summary completed. Next Direction: {next_direction}")
        
        # 將下一輪方向加入歷史，供下一輪 Agent 參考
        self.history.append({"role": "Chairman (Next Direction)", "content": next_direction})
        
        return {
            "round": round_num,
            "team_summaries": round_team_summaries,
            "next_direction": next_direction
        }

    def _generate_team_summary(self, team_name: str, discussion_log: List[str]) -> str:
        """
        生成團隊內部的共識與分歧總結。
        """
        discussion_text = "\n".join(discussion_log)
        
        db = SessionLocal()
        try:
            default_system = "你是 {team_name} 的記錄員。請根據團隊成員的發言，總結本輪討論的「共同觀點」與「內部分歧」。"
            sys_template = PromptService.get_prompt(db, "debate.team_summary_system", default=default_system)
            system_prompt = sys_template.format(team_name=team_name)

            default_user = "討論記錄：\n{discussion_text}\n\n請輸出總結："
            user_template = PromptService.get_prompt(db, "debate.team_summary_user", default=default_user)
            user_prompt = user_template.format(discussion_text=discussion_text)
        finally:
            db.close()
            
        return call_llm(user_prompt, system_prompt=system_prompt)

    def _agent_select_tools(self, agent: AgentBase, side: str):
        """
        Agent 在辯論開始前動態選擇最適合的工具。
        僅展示該 Agent 權限範圍內的工具（Global + Assigned ToolSets）。
        """
        db = SessionLocal()
        try:
            # 獲取該 Agent 可用的工具列表 (從 DB ToolSet)
            agent_id = getattr(agent, 'id', None)
            if not agent_id:
                # 嘗試從 DB 查找
                db_agent = db.query(models.Agent).filter(models.Agent.name == agent.name).first()
                if db_agent:
                    agent_id = db_agent.id
            
            if agent_id:
                available_tools_list = ToolSetService.get_agent_available_tools(db, agent_id)
            else:
                # Fallback: 如果找不到 ID，列出所有工具 (或僅 Global)
                all_tools_dict = tool_registry.list()
                available_tools_list = []
                for name, data in all_tools_dict.items():
                    available_tools_list.append({"name": name, "description": data['description']})

            tools_list_text = "\n".join([f"- {t['name']}: {t['description']}" for t in available_tools_list])
        finally:
            db.close()
        
        # DB session for prompt
        db = SessionLocal()
        try:
            default_system = "你是 {agent_name}，即將代表{side}參加關於「{topic}」的辯論。你的任務是從可用工具庫中選擇對你最有幫助的工具。"
            sys_template = PromptService.get_prompt(db, "debate.tool_selection_system", default=default_system)
            system_prompt = sys_template.format(agent_name=agent.name, side=side, topic=self.topic)

            default_user = """
可用工具列表：
{tools_list_text}

請分析辯題與你的立場，選擇 3-5 個最關鍵的工具。
**重要：** 請仔細查看每個工具描述中的 **Schema**，選擇那些輸入/輸出欄位最符合你數據需求的工具。不要僅憑工具名稱猜測功能。

請直接返回工具名稱的 JSON 列表，例如：["searxng.search", "tej.stock_price"]
不要輸出其他文字。
"""
            user_template = PromptService.get_prompt(db, "debate.tool_selection_user", default=default_user)
            user_prompt = user_template.format(tools_list_text=tools_list_text)
        finally:
            db.close()

        try:
            response = call_llm(user_prompt, system_prompt=system_prompt)
            # 嘗試解析 JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                selected_tools = json.loads(json_match.group(0))
                self.agent_tools_map[agent.name] = selected_tools
                print(f"Agent {agent.name} selected tools: {selected_tools}")
                self._publish_log(f"{agent.name} (Setup)", f"Selected tools: {selected_tools}")
            else:
                print(f"Agent {agent.name} failed to select tools (no JSON), using defaults.")
                self.agent_tools_map[agent.name] = []
        except Exception as e:
            print(f"Error in tool selection for {agent.name}: {e}")
            self.agent_tools_map[agent.name] = []

    def _compress_history(self):
        """
        使用 LLM 壓縮舊的辯論歷史 (Compression 策略)。
        """
        keep_recent = 3
        # 只有當累積的歷史訊息超過一定數量時才觸發壓縮
        if len(self.history) <= keep_recent + 2:
            return

        # 提取需要壓縮的舊訊息
        to_compress = self.history[:-keep_recent]
        # 更新 self.history，只保留最近的訊息
        self.history = self.history[-keep_recent:]
        
        # 構建壓縮 Prompt
        conversation_text = "\n".join([f"{item.get('role')}: {str(item.get('content'))[:500]}" for item in to_compress])
        
        db = SessionLocal()
        try:
            default_system = "你是辯論記錄員。你的任務是將對話歷史壓縮成簡練的摘要，保留關鍵論點和數據，去除冗餘內容。"
            sys_template = PromptService.get_prompt(db, "debate.history_compression_system", default=default_system)
            system_prompt = sys_template

            default_user = "請壓縮以下對話歷史（接續之前的摘要）：\n\n之前的摘要：{compressed_history}\n\n新的對話：\n{conversation_text}"
            user_template = PromptService.get_prompt(db, "debate.history_compression_user", default=default_user)
            user_prompt = user_template.format(compressed_history=self.compressed_history, conversation_text=conversation_text)
        finally:
            db.close()
        
        try:
            summary = call_llm(user_prompt, system_prompt=system_prompt)
            if summary:
                self.compressed_history = summary
                print(f"DEBUG: History compressed. New summary length: {len(summary)}")
                self._publish_log("System", "已對舊的辯論歷史進行壓縮處理。")
        except Exception as e:
            print(f"WARNING: History compression failed: {e}")

    def _get_compact_history(self, max_length=2000) -> str:
        """
        獲取優化後的辯論歷史 (ReMe 策略：Compression + Smart Retention)
        """
        # 1. 嘗試觸發壓縮 (Compression)
        self._compress_history()
        
        # 2. 構建近期完整歷史 (Smart Retention)
        active_history_text = ""
        for item in self.history:
            content = item.get("content", "")
            # 對於近期的 Tool Output，如果太長也進行簡單截斷 (Compaction)
            if len(content) > 800:
                content = content[:300] + "...(略)..." + content[-300:]
            active_history_text += f"{item.get('role')}: {content}\n\n"
        
        full_text = f"【早期辯論摘要】：\n{self.compressed_history}\n\n【近期對話】：\n{active_history_text}"
        return full_text

    def _agent_turn(self, agent: AgentBase, side: str, round_num: int) -> str:
        """
        執行單個 Agent 的回合：思考 -> 工具 -> 發言
        """
        print(f"Agent {agent.name} ({side}) is thinking...")
        
        # 構建 Prompt - 使用 Agent 自己選擇的工具
        selected_tool_names = self.agent_tools_map.get(agent.name, [])
        
        # 如果有選擇，則只顯示選擇的工具；否則顯示所有「可用」的工具
        if selected_tool_names:
            all_tools = tool_registry.list()
            filtered_tools = {k: v for k, v in all_tools.items() if k in selected_tool_names}
            
            if not filtered_tools:
                 # 如果選擇無效，回退到顯示該 Agent 所有可用的工具 (ToolSet)
                 tools_desc = get_tools_description()
            else:
                 tools_desc = "你已選擇並激活以下工具：\n" + "\n".join([f"### {name}\n{data['description']}\nSchema: {json.dumps(data['schema'], ensure_ascii=False)}" for name, data in filtered_tools.items()])
        else:
            # 如果沒有選擇（例如初始化失敗），顯示所有工具
            tools_desc = get_tools_description()
            
        # Append Meta-Tool Description
        tools_desc += "\n\n### reset_equipped_tools\nDescription: 動態切換工具組 (active tool group)。\nParameters: {'group': 'browser_use' | 'financial_data' | 'basic'}"

        tools_examples = get_tools_examples() # Examples 暫時保持全集，或者也可以過濾
        
        # Retrieve Tool LTM hints
        tool_hints = ""
        with ReMeToolLongTermMemory() as tool_mem:
            tool_hints = tool_mem.retrieve(self.topic) # Use topic as context for now
            if tool_hints:
                tools_examples += f"\n\n**過往成功工具調用參考 (ReMe Tool LTM)**:\n{tool_hints}"

        history_text = self._get_compact_history()
        
        db = SessionLocal()
        try:
            # 1. System Prompt
            default_system = """你是 {agent_name}，代表{side}。
辯題：{topic}

**重要指示**：
1. 你必須先使用工具獲取真實數據，再發表論點
2. **精準調用**：請仔細閱讀所有可用工具的 **Schema** (欄位說明)，選擇最能提供你所需數據的工具。對於金融數據，務必確認工具包含你需要的特定指標。
3. **時間因子**：如果工具包含時間參數（如 start_date, end_date, mdate），請務必根據問題中的時間描述（如「近一年」、「2024 Q1」）計算並填入準確的日期範圍，不要省略。
4. 工具調用格式必須是純 JSON，不要有其他文字
5. 調用工具後，你會收到數據，然後基於數據發言
"""
            sys_template = PromptService.get_prompt(db, "debater.system_instruction", default=default_system)
            system_prompt = sys_template.format(agent_name=agent.name, side=side, topic=self.topic)

            # 2. User Prompt (Tool Instruction)
            default_user = """
这是第 {round_num} 輪辯論。

**辯論歷史摘要**：
{history_text}

**主席戰略摘要**：{chairman_summary}

**背景資訊**：
- 當前日期：{current_date}
- 辯題涉及：2024 年 Q4（2024-10-01 至 2024-12-31）
- 你需要查詢 2024 年的實際股價數據進行比較

**重要常數**：
{stock_codes}

**第一步：必須先調用工具獲取數據**

{tools_desc}

{tools_examples}

**請現在就調用工具**（只輸出 JSON，不要其他文字）：
"""
            user_template = PromptService.get_prompt(db, "debater.tool_instruction", default=default_user)
            user_prompt = user_template.format(
                round_num=round_num,
                history_text=history_text,
                chairman_summary=self.analysis_result.get('step5_summary', '無'),
                current_date=CURRENT_DATE,
                stock_codes=chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                tools_desc=tools_desc,
                tools_examples=tools_examples
            )
        finally:
            db.close()
        
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
            # 嘗試提取 JSON (支援純 JSON 或混在文字中的 JSON)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print(f"DEBUG: Extracted JSON string: {json_str[:200]}...")
                
                try:
                    tool_call = json.loads(json_str)
                    print(f"DEBUG: Successfully parsed JSON: {tool_call}")
                except json.JSONDecodeError as e:
                    print(f"WARNING: JSON decode failed: {e}")
                    print(f"DEBUG: Failed JSON string: {json_str}")
                    # 如果解析失敗，視為普通文本回應
                    return response

                if isinstance(tool_call, dict) and "tool" in tool_call and "params" in tool_call:
                    tool_name = tool_call["tool"]
                    params = tool_call["params"]
                    
                    # --- Meta-Tool: reset_equipped_tools ---
                    if tool_name == "reset_equipped_tools":
                        target_group = params.get("group", "basic")
                        print(f"⚙️ Agent {agent.name} is resetting equipped tools to group: {target_group}")
                        self._publish_log(f"{agent.name} (Meta-Tool)", f"Resetting tools to group: {target_group}")
                        
                        # Update Agent's tool selection
                        # Get all tools in this group
                        group_tools = tool_registry.list(groups=[target_group])
                        self.agent_tools_map[agent.name] = list(group_tools.keys())
                        
                        # Re-prompt agent with new tools (Recursive call or loop? Loop is safer)
                        # We return a special indicator to the caller (or just recurse)
                        # Here, we'll just return a system message saying tools updated,
                        # and rely on the next turn (or re-prompt immediately if structure allows).
                        # Ideally, we should re-run the turn logic.
                        # For simplicity, let's recurse once.
                        return self._agent_turn(agent, side, round_num)
                    
                    print(f"✓ Agent {agent.name} is calling tool: {tool_name}")
                    print(f"✓ Tool parameters: {json.dumps(params, ensure_ascii=False)}")
                    self._publish_log(f"{agent.name} (Tool)", f"Calling {tool_name} with {params}")
                    
                    # 執行工具 (支援所有註冊的工具)
                    try:
                        print(f"DEBUG: Executing tool {tool_name}...")
                        from worker import tasks  # Lazy import to avoid circular dependency
                        tool_result = tasks.execute_tool(tool_name, params)
                        print(f"✓ Tool execution successful")
                        print(f"DEBUG: Tool result preview: {str(tool_result)[:300]}...")
                        
                        # Record successful tool usage to Tool LTM
                        with ReMeToolLongTermMemory() as tool_mem:
                            tool_mem.record(
                                intent=f"Debate on {self.topic}",
                                tool_name=tool_name,
                                params=params,
                                result=tool_result,
                                success=True
                            )

                    except Exception as e:
                        tool_result = {"error": f"Tool execution error: {str(e)}"}
                        print(f"ERROR: Tool {tool_name} execution failed: {e}")
                        
                        # Record failed tool usage
                        with ReMeToolLongTermMemory() as tool_mem:
                            tool_mem.record(
                                intent=f"Debate on {self.topic}",
                                tool_name=tool_name,
                                params=params,
                                result=str(e),
                                success=False
                            )
                    
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
