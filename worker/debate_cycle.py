from typing import List, Dict, Any
from worker.chairman import Chairman
from agentscope.agent import AgentBase
import json
import re
import os
import sys
import yaml
import asyncio
import resource
from datetime import datetime
from worker.llm_utils import call_llm, call_llm_async
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from worker.memory import ReMePersonalLongTermMemory, ReMeTaskLongTermMemory, ReMeToolLongTermMemory
from api.tool_registry import tool_registry
from api.toolset_service import ToolSetService
from api.redis_client import get_redis_client

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
        self.redis_client = get_redis_client()
        self.evidence_key = f"debate:{self.debate_id}:evidence"
        self.rounds_data = []
        self.analysis_result = {}
        self.history = []
        self.full_history = []  # 完整歷史記錄（不壓縮，用於報告）
        self.compressed_history = "無"  # 存儲 LLM 壓縮後的歷史摘要
        self.agent_tools_map = {} # 存儲每個 Agent 選擇的工具列表

    def _get_memory_usage(self) -> str:
        """獲取當前記憶體使用量 (MB)"""
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # MacOS: bytes, Linux: KB
            if sys.platform == 'darwin':
                return f"{usage / 1024 / 1024:.2f} MB"
            return f"{usage / 1024:.2f} MB"
        except Exception:
            return "N/A"

    def _publish_log(self, role: str, content: str):
        """
        發布日誌到 Redis，供前端 SSE 訂閱。
        """
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", message)

    def _publish_progress(self, percentage: int, message: str, stage: str = "setup"):
        """
        發布進度更新事件，供前端顯示進度條。
        """
        event_data = {
            "type": "progress_update",
            "progress": percentage,
            "message": message,
            "stage": stage,
            "timestamp": datetime.now().isoformat()
        }
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", json.dumps(event_data, ensure_ascii=False))

    def _save_report_to_file(self, conclusion: str, jury_report: str = None):
        """
        將辯論過程保存為 Markdown 文件。
        """
        import re
        from datetime import datetime
        
        report_dir = "data/replays"
        os.makedirs(report_dir, exist_ok=True)
        
        # 清理題目，移除非法文件名字符
        safe_topic = re.sub(r'[<>:"/\\|?*]', '', self.topic)
        safe_topic = safe_topic.replace(' ', '_')[:50]  # 限制長度
        
        # 生成時間戳（可讀格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 組合檔名：題目_時間.md
        filename = f"{safe_topic}_{timestamp}.md"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 辯論報告：{self.topic}\n\n")
            f.write(f"**ID**: {self.debate_id}\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 🏆 最終結論\n\n")
            f.write(f"{conclusion}\n\n")

            if jury_report:
                f.write("## ⚖️ 評審團評估報告\n\n")
                f.write(f"{jury_report}\n\n")
            
            f.write("## 📝 辯論過程記錄\n\n")
            for item in self.full_history:
                role = item.get("role", "Unknown")
                content = item.get("content", "")
                f.write(f"### {role}\n")
                f.write(f"{content}\n\n")
                f.write("---\n\n")
                
        print(f"Report saved to {filepath}")

    def start(self) -> Dict[str, Any]:
        """
        开始辩论循环 (Sync wrapper around async start).
        """
        return asyncio.run(self.start_async())

    async def start_async(self) -> Dict[str, Any]:
        """
        开始辩论循环 (Async).
        """
        print(f"Debate '{self.debate_id}' has started. Mem: {self._get_memory_usage()}")
        self._publish_log("System", f"Debate '{self.debate_id}' has started.")
        self._publish_progress(5, "初始化辯論環境...", "init")
        
        # 0. 賽前分析
        # Check Task LTM for similar past debates
        with ReMeTaskLongTermMemory() as task_mem:
            similar_tasks = task_mem.retrieve_similar_tasks(self.topic)
            if similar_tasks:
                print(f"DEBUG: Found similar past debates:\n{similar_tasks}")
                self._publish_log("System", f"Found similar past debates:\n{similar_tasks}")

        self._publish_progress(10, "主席正在進行賽前分析...", "analysis")
        
        # Note: Chairman analysis is still sync for now as it's complex, but could be made async too.
        self.analysis_result = self.chairman.pre_debate_analysis(self.topic)
        summary = self.analysis_result.get('step5_summary', '無')
        self.chairman.speak(f"賽前分析完成。戰略摘要：{summary}")
        self._publish_log("Chairman (Analysis)", f"賽前分析完成。\n戰略摘要：{summary}")
        
        self._publish_progress(30, "分析完成，準備 Agent 工具...", "tool_selection")
        
        # 1. Agent 動態選擇工具 (Initialization Phase)
        print("Agents are selecting their tools...")
        self._publish_log("System", "🎯 辯論準備階段：各 Agent 正在選擇最適合的工具...")
        
        total_agents = sum(len(team['agents']) for team in self.teams)
        if total_agents == 0:
            total_agents = 1 # Avoid division by zero
        
        # Run tool selection sequentially
        self._publish_log("System", f"🚀 啟動 {total_agents} 個 Agent 順序工具選擇...")
        
        agent_processed_count = 0
        for team in self.teams:
            side = team.get('side', 'neutral')
            for agent in team['agents']:
                 await self._agent_select_tools_async(agent, side)
                 agent_processed_count += 1
                 # Calculate progress from 30% to 90%
                 progress = 30 + int((agent_processed_count / total_agents) * 60)
                 self._publish_progress(progress, f"Agent {agent.name} 工具配置完成 ({agent_processed_count}/{total_agents})", "tool_selection")

        self._publish_log("System", "✅ 所有 Agent 工具選擇完成。")
        self._publish_progress(100, "準備就緒，辯論開始！", "start")

        
        for i in range(1, self.rounds + 1):
            print(f"--- Round {i} --- (Mem: {self._get_memory_usage()})")
            self._publish_log("System", f"--- Round {i} ---")
            round_result = await self._run_round_async(i)
            self.rounds_data.append(round_result)
        
        # 4. 最終總結
        handcard = self.analysis_result.get('step6_handcard') or self.analysis_result.get('step5_summary', '無手卡')
        final_conclusion = self.chairman.summarize_debate(self.debate_id, self.topic, self.rounds_data, handcard)
        self._publish_log("Chairman (Conclusion)", final_conclusion)

        # 5. Jury 評估
        jury_report = self._run_jury_evaluation(final_conclusion)

        # Record outcome to Task LTM
        with ReMeTaskLongTermMemory() as task_mem:
            task_mem.record(self.topic, final_conclusion)
            
        # Save to File (Markdown Report)
        self._save_report_to_file(final_conclusion, jury_report)

        print(f"Debate '{self.debate_id}' has ended.")
        self._publish_log("System", f"Debate '{self.debate_id}' has ended.")
        
        return {
            "topic": self.topic,
            "rounds_data": self.rounds_data,
            "analysis": self.analysis_result,
            "final_conclusion": final_conclusion,
            "jury_report": jury_report
        }

    def _run_jury_evaluation(self, final_conclusion: str) -> str:
        """
        執行評審團 (Jury) 評估，生成評分與分析報告。
        """
        print("Jury is evaluating the debate...")
        self._publish_log("System", "評審團正在進行最終評估...")

        try:
            # Load Jury System Prompt (Priority: PromptService -> File -> Default)
            file_system_prompt = "你是辯論評審團。"
            try:
                with open("prompts/agents/jury.yaml", "r", encoding="utf-8") as f:
                    jury_config = yaml.safe_load(f)
                    file_system_prompt = jury_config.get("system_prompt", file_system_prompt)
            except Exception as e:
                print(f"Warning: Failed to load jury.yaml: {e}")

            db = SessionLocal()
            try:
                system_prompt = PromptService.get_prompt(db, "jury.system_prompt", default=file_system_prompt)
            finally:
                db.close()
            
            # 構建完整辯論記錄文字
            debate_log = ""
            for item in self.full_history:
                role = item.get("role", "Unknown")
                content = item.get("content", "")
                debate_log += f"[{role}]: {content}\n\n"
                
            debate_log += f"[Chairman Final Conclusion]: {final_conclusion}\n"

            user_prompt = f"""
請根據以下完整的辯論記錄，生成「最終評估報告」。

**重要：請使用繁體中文撰寫評估報告。**

辯題：{self.topic}

辯論記錄：
{debate_log}

請按照 System Prompt 的要求，輸出包含評分表與文字分析的報告。
"""
            # Call LLM
            jury_report = call_llm(user_prompt, system_prompt=system_prompt)
            
            self._publish_log("Jury", jury_report)
            print("Jury evaluation completed.")
            return jury_report
            
        except Exception as e:
            error_msg = f"Jury evaluation failed: {str(e)}"
            print(error_msg)
            self._publish_log("System", error_msg)
            return error_msg

    def _update_team_score(self, side: str, delta: float, reason: str):
        """
        更新團隊評分並推送通知。
        """
        score_key = f"debate:{self.debate_id}:scores"
        # Initial scores if not set (default 100)
        if not self.redis_client.hexists(score_key, side):
            self.redis_client.hset(score_key, side, 100.0)
        
        new_score = self.redis_client.hincrbyfloat(score_key, side, delta)
        
        # Publish score update event
        event_data = {
            "type": "score_update",
            "side": side,
            "new_score": new_score,
            "delta": delta,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", json.dumps(event_data, ensure_ascii=False))
        self._publish_log("System (Score)", f"⚖️ 【{side}】分數變更: {delta} ({reason}) => 當前分數: {new_score}")

    def _neutral_verification_turn(self, agent: AgentBase, team_name: str, round_num: int) -> str:
        return asyncio.run(self._neutral_verification_turn_async(agent, team_name, round_num))

    async def _neutral_verification_turn_async(self, agent: AgentBase, team_name: str, round_num: int) -> str:
        """
        中立方的特殊回合：核實證據並進行評分 (Async)。
        """
        print(f"Neutral Agent {agent.name} is verifying evidence...")
        self._publish_log(f"{agent.name} (Verification)", "🔍 正在審查各方提出的證據進行核實...")

        # 1. Fetch unverified evidence from Redis
        all_evidence = [json.loads(e) for e in self.redis_client.lrange(self.evidence_key, 0, -1)]
        # Filter: from current round (or previous), not neutral, not verified
        target_evidence = [e for e in all_evidence if e.get('side') != 'neutral' and not e.get('verified', False)]
        
        verification_report = ""
        
        if not target_evidence:
            return await self._agent_turn_async(agent, 'neutral', round_num) # Fallback to normal turn if no evidence

        # 2. Verify each evidence (Limit to 1-2 to save time/cost)
        for ev in target_evidence[:2]:
            tool_name = ev.get('tool')
            params = ev.get('params')
            original_result = ev.get('result')
            provider_side = ev.get('side', 'Unknown')
            
            self._publish_log(f"{agent.name} (Verification)", f"正在核實 {provider_side} 方使用的工具: {tool_name}...")
            
            try:
                # Re-execute tool
                from worker import tasks
                # Execute sync tool in thread pool
                loop = asyncio.get_running_loop()
                verify_result = await loop.run_in_executor(None, tasks.execute_tool, tool_name, params)
                
                # Simple comparison (Equality check might be too strict for some dynamic data, but good for now)
                # Ideally, we ask LLM to compare.
                
                # Construct verification prompt
                comparison_prompt = f"""
請比較以下兩次工具調用的結果，判斷是否一致，以及原始引用是否準確。

工具：{tool_name}
參數：{params}

原始結果（由 {provider_side} 方提供）：
{str(original_result)[:1000]}...

核實結果（由中立方重新執行）：
{str(verify_result)[:1000]}...

請輸出 JSON：
{{
    "consistent": true/false,
    "score_penalty": 0 到 -10,
    "comment": "簡短評語"
}}
"""
                # Call LLM for judgement
                judge_response = await call_llm_async(comparison_prompt, system_prompt="你是公正的數據核實員。")
                
                # Parse JSON
                try:
                    # Robust JSON extraction
                    json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
                    if json_match:
                        judge_json = json.loads(json_match.group(0))
                        
                        consistent = judge_json.get('consistent', True)
                        penalty = judge_json.get('score_penalty', 0)
                        comment = judge_json.get('comment', '')
                        
                        if consistent:
                            verification_report += f"- ✅ 核實通過 ({tool_name}): 數據一致。\n"
                        else:
                            verification_report += f"- ❌ 核實失敗 ({tool_name}): {comment} (扣分: {penalty})\n"
                            if penalty < 0:
                                self._update_team_score(provider_side, float(penalty), f"證據核實失敗: {comment}")
                    else:
                        verification_report += f"- ⚠️ 無法判斷 ({tool_name}): {judge_response[:50]}\n"

                except Exception as e:
                    print(f"Verification judgment parsing error: {e}")
                    verification_report += f"- ⚠️ 核實判讀錯誤 ({tool_name})\n"

            except Exception as e:
                verification_report += f"- ⚠️ 工具重跑失敗 ({tool_name}): {e}\n"

        # 3. Generate Speech based on verification
        final_prompt = f"""
你是中立方辯手 {agent.name}。
這是第 {round_num} 輪。

你的核心任務是擔任「事實查核者」。
你剛剛對其他團隊的證據進行了核實，結果如下：
{verification_report}

請基於以上核實結果，發表你的觀點。
1. 如果有核實失敗，嚴厲指出並批評。
2. 如果數據都可靠，則針對辯題發表中立分析。
3. 保持客觀、公正。
"""
        response = await call_llm_async(final_prompt, system_prompt=f"你是 {agent.name}，公正的第三方。")
        return response

    def _run_round(self, round_num: int) -> Dict[str, Any]:
         """Sync wrapper around async _run_round_async"""
         return asyncio.run(self._run_round_async(round_num))

    async def _run_round_async(self, round_num: int) -> Dict[str, Any]:
        """
        运行一轮辩论 (Async, Parallel Team Execution).
        包含：各團隊內部討論 (Parallel) -> 團隊總結 -> 主席彙整與下一輪引導
        """
        from worker import tasks # Lazy import to avoid circular dependency
        
        # 1. 主席引导
        opening = f"现在開始第 {round_num} 輪辯論。"
        self.chairman.speak(opening)
        self.history.append({"role": "Chairman", "content": opening})
        self.full_history.append({"role": "Chairman", "content": opening})
        self._publish_log("Chairman", opening)

        # 2. 各團隊內部辯論與總結 (Intra-Team Debate & Summary)
        round_team_summaries = {}
        
        total_teams = len(self.teams)
        
        # Run all teams sequentially
        self._publish_log("System", f"🚀 啟動 {total_teams} 隊順序討論...")
        team_results = []
        for team in self.teams:
            result = await self._process_team_deliberation(team, round_num)
            team_results.append(result)
        
        # Process results from all teams
        for team_result in team_results:
            team_name = team_result['name']
            team_summary = team_result['summary']
            discussion_log = team_result['log']
            
            round_team_summaries[team_name] = team_summary
            
            # Store history (Note: Order might be mixed in real-time logs, but here we append block by block)
            # Ideally, we want to interleave them in history based on timestamp, but for simplicity:
            for item in discussion_log:
                 self.history.append(item)
                 self.full_history.append(item)
            
            self.history.append({"role": f"{team_name} Summary", "content": team_summary})
            self.full_history.append({"role": f"{team_name} Summary", "content": team_summary})
            
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
        self.full_history.append({"role": "Chairman (Next Direction)", "content": next_direction})
        
        return {
            "round": round_num,
            "team_summaries": round_team_summaries,
            "next_direction": next_direction
        }
        
    async def _process_team_deliberation(self, team: Dict, round_num: int) -> Dict[str, Any]:
        """
        Process a single team's deliberation asynchronously.
        """
        team_name = team['name']
        team_side = team.get('side', 'neutral')
        team_agents = team['agents']
        total_agents_in_team = len(team_agents)
        
        team_icon = "🟦" if team_side == "pro" else "🟥" if team_side == "con" else "🟩"
        self._publish_log("System", f"{team_icon} 【{team_name}】開始內部討論...")
        
        team_discussion_log_text = [] # For summary generation
        team_history_entries = [] # For returning to main thread
        
        # Within a team, agents might still need to speak in order, OR parallel?
        # Usually debate implies responding to each other.
        # However, "Intra-Team Debate" in this simplified version is just each agent speaking once.
        # We can make agents within a team parallel too!
        
        agent_results = []
        for agent in team_agents:
            if team_side == "neutral":
                 content = await self._neutral_verification_turn_async(agent, team_name, round_num)
            else:
                 content = await self._agent_turn_async(agent, team_name, round_num)
            agent_results.append(content)
        
        for idx, (agent, content) in enumerate(zip(team_agents, agent_results)):
             role_label = f"{team_name} - {agent.name}"
             
             entry = {"role": role_label, "content": content}
             team_history_entries.append(entry)
             team_discussion_log_text.append(f"{agent.name}: {content}")
             
             # Publish individual log (Note: Might arrive out of order visually if not carefully handled on frontend,
             # but here we publish as soon as done)
             self._publish_log(role_label, content)

        # 生成團隊共識與分歧總結
        self._publish_log("System", f"📊 {team_name} 正在整理團隊共識...")
        team_summary = await self._generate_team_summary_async(team_name, team_discussion_log_text)
        self._publish_log(f"{team_name} (Summary)", team_summary)
        
        return {
            "name": team_name,
            "summary": team_summary,
            "log": team_history_entries
        }

    def _generate_team_summary(self, team_name: str, discussion_log: List[str]) -> str:
         return asyncio.run(self._generate_team_summary_async(team_name, discussion_log))

    async def _generate_team_summary_async(self, team_name: str, discussion_log: List[str]) -> str:
        """
        生成團隊內部的共識與分歧總結 (Async).
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
            
        return await call_llm_async(user_prompt, system_prompt=system_prompt)

    def _agent_select_tools(self, agent: AgentBase, side: str):
         """Sync wrapper for backward compatibility"""
         return asyncio.run(self._agent_select_tools_async(agent, side))

    async def _agent_select_tools_async(self, agent: AgentBase, side: str):
        """
        Agent 在辯論開始前動態選擇最適合的工具 (Async)。
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
            # Async LLM Call
            response = await call_llm_async(user_prompt, system_prompt=system_prompt)
            
            # 嘗試解析 JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                selected_tools = json.loads(json_match.group(0))
                self.agent_tools_map[agent.name] = selected_tools
                print(f"Agent {agent.name} selected tools: {selected_tools}")
                
                # 格式化工具列表顯示
                tools_display = "\n".join([f"  • {tool}" for tool in selected_tools])
                self._publish_log(f"{agent.name} (Setup)", f"✅ 已選擇 {len(selected_tools)} 個工具：\n{tools_display}")
            else:
                print(f"Agent {agent.name} failed to select tools (no JSON), using defaults.")
                self.agent_tools_map[agent.name] = []
                self._publish_log(f"{agent.name} (Setup)", "⚠️ 工具選擇失敗，將使用默認配置")
        except Exception as e:
            print(f"Error in tool selection for {agent.name}: {e}")
            self.agent_tools_map[agent.name] = []
            self._publish_log(f"{agent.name} (Setup)", f"❌ 工具選擇錯誤: {str(e)}")

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
        return asyncio.run(self._agent_turn_async(agent, side, round_num))

    async def _agent_turn_async(self, agent: AgentBase, side: str, round_num: int) -> str:
        """
        執行單個 Agent 的回合：思考 -> 工具 -> 發言 (Async)
        """
        print(f"Agent {agent.name} ({side}) is thinking...")
        self._publish_log(f"{agent.name} (Thinking)", f"{agent.name} 正在思考並決定使用的策略...")
        
        # 構建 Prompt - 使用 Agent 自己選擇的工具
        selected_tool_names = self.agent_tools_map.get(agent.name, [])
        
        # 如果有選擇，則只顯示選擇的工具；否則顯示所有「可用」的工具
        if selected_tool_names:
            filtered_tools = {}
            for name in selected_tool_names:
                try:
                    # Using get_tool_data ensures lazy tools are loaded and schema is available
                    # Assuming version 'v1' for now as selection doesn't specify version
                    tool_data = tool_registry.get_tool_data(name)
                    filtered_tools[name] = tool_data
                except Exception as e:
                    print(f"Warning: Selected tool '{name}' not found or failed to load: {e}")

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
        
        # Append Chairman Intervention Tool (Virtual)
        tools_desc += "\n\n### call_chairman\nDescription: 當你發現辯題資訊嚴重不足（如缺乏背景、定義不清），無法進行有效分析時，請使用此工具通知主席介入處理。\nParameters: {'reason': '說明具體缺少什麼資訊或背景'}"

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
            # 1. System Prompt Construction
            # Strategy: Combine Agent's Custom Persona with System's Operational Rules
            
            # A. Operational Rules (Mandatory)
            operational_rules = """
**系統操作規範 (Operational Rules)**：
1. **工具優先**：必須先使用工具獲取真實數據，再發表論點。
2. **精準調用**：仔細閱讀工具 Schema。TEJ 工具必須提供 `coid` (公司代碼)，請參考【重要常數】。
3. **時間感知**：工具日期參數 (start_date/end_date) 必須根據問題時間動態計算，不可省略。
4. **輸出格式**：調用工具時，必須輸出純 JSON，不要包含 Markdown 代碼塊或其他文字。
"""
            
            # B. Agent Persona (Custom or Default)
            custom_prompt = getattr(agent, 'system_prompt', '').strip()
            if custom_prompt:
                persona_section = f"""
**你的角色設定 (Persona)**：
{custom_prompt}

你是 {agent.name}，代表 {side} 方。
辯題：{self.topic}
"""
            else:
                persona_section = f"""
**你的角色設定 (Persona)**：
你是 {agent.name}，代表 {side} 方。
辯題：{self.topic}
"""

            # Combine
            default_system = f"{persona_section}\n{operational_rules}"
            
            # Try to get override from DB, but prioritize constructing it dynamically if not found
            # Note: We don't use PromptService here for the full prompt to avoid losing the dynamic custom_prompt.
            # However, if we want to allow DB overrides of the *structure*, we could.
            # For now, let's stick to the dynamic construction to ensure custom prompts work.
            system_prompt = default_system

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
        
        # Async LLM Call
        response = await call_llm_async(user_prompt, system_prompt=system_prompt)
        print(f"DEBUG: Agent {agent.name} raw response: {response[:500]}")  # 只印前 500 字符

        # Retry 機制
        if not response:
            print(f"WARNING: Empty response from {agent.name}, retrying with simple prompt...")
            retry_prompt = f"請針對辯題「{self.topic}」發表你的{side}論點。請務必使用繁體中文。"
            response = await call_llm_async(retry_prompt, system_prompt=system_prompt)
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

                if isinstance(tool_call, dict) and "error" in tool_call:
                    error_msg = tool_call["error"]
                    print(f"WARNING: Agent returned error JSON: {error_msg}")
                    # 自動重試機制：強制引導使用搜尋工具
                    if "未提供具體任務" in str(error_msg) or "無法確定" in str(error_msg):
                        retry_prompt = f"""你似乎不確定該做什麼。請作為{side}方，針對辯題「{self.topic}」進行事實查核。
請務必調用 `searxng.search` 工具，查詢相關新聞或數據。
例：{{"tool": "searxng.search", "params": {{"q": "{self.topic} 爭議點"}}}}"""
                        print(f"DEBUG: Auto-retrying with guidance...")
                        return await call_llm_async(retry_prompt, system_prompt=system_prompt)
                
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
                        return await self._agent_turn_async(agent, side, round_num)

                    # --- Meta-Tool: call_chairman (Intervention) ---
                    if tool_name == "call_chairman":
                        reason = params.get("reason", "未說明原因")
                        print(f"🚨 Agent {agent.name} is calling Chairman for help: {reason}")
                        self._publish_log(f"{agent.name} (SOS)", f"請求主席介入：{reason}")

                        # 1. Chairman generates clarification
                        chairman_prompt = f"""
Agent {agent.name} ({side}方) 在分析辯題「{self.topic}」時遇到困難。
回報原因：{reason}

請根據你的賽前分析手卡（Handcard），為該 Agent 提供一段「背景補充說明」或「引導指示」。
請保持簡短、明確，幫助它繼續進行分析。
"""
                        clarification = await call_llm_async(chairman_prompt, system_prompt="你是辯論主席。你的任務是協助遇到困難的辯手，提供必要的背景資訊引導，但不要直接替它辯論。")
                        
                        self._publish_log("Chairman (Intervention)", f"主席回應：{clarification}")
                        print(f"💡 Chairman provided clarification: {clarification}")

                        # 2. Retry Agent Turn with Clarification
                        # We need to inject this clarification into the next prompt.
                        # For simplicity, we can recurse but append the clarification to history or a special context.
                        # Here we append it to history temporarily for the retry.
                        
                        intervention_msg = {"role": "Chairman (Intervention)", "content": f"針對你的問題「{reason}」，補充說明如下：\n{clarification}\n\n請根據此資訊繼續你的分析。"}
                        self.history.append(intervention_msg)
                        
                        # Retry
                        return await self._agent_turn_async(agent, side, round_num)
                    
                    print(f"✓ Agent {agent.name} is calling tool: {tool_name}")
                    print(f"✓ Tool parameters: {json.dumps(params, ensure_ascii=False)}")
                    self._publish_log(f"{agent.name} (Tool)", f"Calling {tool_name} with {params}")
                    
                    # 執行工具 (支援所有註冊的工具)
                    # Note: Tools might still be sync (requests). We run them in executor to avoid blocking loop.
                    try:
                        print(f"DEBUG: Executing tool {tool_name}...")
                        from worker import tasks  # Lazy import to avoid circular dependency
                        
                        # Execute sync tool in thread pool
                        loop = asyncio.get_running_loop()
                        tool_result = await loop.run_in_executor(None, tasks.execute_tool, tool_name, params)
                        
                        print(f"✓ Tool execution successful")
                        print(f"DEBUG: Tool result preview: {str(tool_result)[:300]}...")
                        self._publish_log(f"{agent.name} (Tool)", f"工具 {tool_name} 執行成功獲取數據。")
                        
                        # Record successful tool usage to Tool LTM
                        with ReMeToolLongTermMemory() as tool_mem:
                            tool_mem.record(
                                intent=f"Debate on {self.topic}",
                                tool_name=tool_name,
                                params=params,
                                result=tool_result,
                                success=True
                            )
                        
                        # --- Evidence Recording for Neutral Verification ---
                        # Record full evidence details to Redis for verification
                        evidence_entry = {
                            "role": f"{agent.name} ({side})",
                            "agent_name": agent.name,
                            "side": side,
                            "tool": tool_name,
                            "params": params,
                            "result": tool_result,
                            "timestamp": datetime.now().isoformat(),
                            "verified": False,
                            "round": round_num
                        }
                        self.redis_client.rpush(self.evidence_key, json.dumps(evidence_entry, ensure_ascii=False))
                        # ------------------------------------------------

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
                    final_response = await call_llm_async(prompt_with_tool, system_prompt=system_prompt)
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
