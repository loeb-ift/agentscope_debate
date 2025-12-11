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
import difflib
from datetime import datetime
from worker.llm_utils import call_llm, call_llm_async
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from worker.memory import ReMePersonalLongTermMemory, ReMeTaskLongTermMemory, ReMeToolLongTermMemory, ReMeHistoryMemory, HippocampalMemory
from api.tool_registry import tool_registry
from api.toolset_service import ToolSetService
from api.redis_client import get_redis_client
from api import models

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
        self.compressed_history = "無"  # 存儲 LLM 壓縮後的歷史摘要 (Legacy)
        self.archived_summaries = [] # List of structured summaries
        self.agent_tools_map = {} # 存儲每個 Agent 選擇的工具列表
        self.hippocampus = HippocampalMemory(debate_id) # Init Hippocampal Memory

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

    def _save_report_to_file(self, conclusion: str, jury_report: str = None, start_time: datetime = None, end_time: datetime = None):
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
            
            # Duration Stats
            if start_time and end_time:
                duration = end_time - start_time
                f.write("## ⏱️ 統計資訊\n")
                f.write(f"- **開始時間**: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"- **結束時間**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"- **總耗時**: {str(duration).split('.')[0]}\n")
                
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
        start_time = datetime.now()
        print(f"Debate '{self.debate_id}' has started. Mem: {self._get_memory_usage()}")
        self._publish_log("System", f"Debate '{self.debate_id}' has started.")
        self._publish_progress(5, "初始化辯論環境...", "init")
        
        # 0. 賽前分析
        # Check Task LTM for similar past debates
        # [OPTIONAL] Disabled to avoid cold-start issues if not required
        # task_mem = ReMeTaskLongTermMemory()
        # similar_tasks = await task_mem.retrieve_similar_tasks_async(self.topic)
        # if similar_tasks:
        #     print(f"DEBUG: Found similar past debates:\n{similar_tasks}")
        #     self._publish_log("System", f"Found similar past debates:\n{similar_tasks}")

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
        # [OPTIONAL] Disabled as debates are independent and history is not required
        # task_mem = ReMeTaskLongTermMemory()
        # await task_mem.record_async(self.topic, final_conclusion)
        
        end_time = datetime.now()
        # Save to File (Markdown Report)
        self._save_report_to_file(final_conclusion, jury_report, start_time, end_time)

        print(f"Debate '{self.debate_id}' has ended.")
        self._publish_log("System", f"Debate '{self.debate_id}' has ended.")
        
        # [CLEANUP] Clear Semantic Cache for this debate
        try:
            from api.vector_store import VectorStore
            await VectorStore.delete_by_filter(
                collection_name="llm_semantic_cache",
                filter_conditions={"context": self.debate_id}
            )
            print(f"DEBUG: Cleared semantic cache for debate {self.debate_id}")
        except Exception as e:
            print(f"WARNING: Failed to clear semantic cache: {e}")

        # Send explicit DONE signal to close the stream
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", "[DONE]")
        
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
            # Load Jury System Prompt
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
                
                # Load User Prompt Template (Moved from hardcoded)
                user_template = PromptService.get_prompt(db, "debate.jury_evaluation_user")
                if not user_template:
                    user_template = "請評估以下辯論：\n{debate_log}" # Minimal fallback
            finally:
                db.close()
            
            # 構建完整辯論記錄文字
            debate_log = ""
            for item in self.full_history:
                role = item.get("role", "Unknown")
                content = item.get("content", "")
                debate_log += f"[{role}]: {content}\n\n"
                
            debate_log += f"[Chairman Final Conclusion]: {final_conclusion}\n"

            # Fill template
            user_prompt = user_template.format(topic=self.topic, debate_log=debate_log)

            # Call LLM
            jury_report = call_llm(user_prompt, system_prompt=system_prompt)
            # Note: Sync call_llm doesn't support context_tag yet, but jury uses sync wrapper?
            # Wait, `call_llm` is sync. `_run_jury_evaluation` uses `call_llm` (sync).
            # The async `call_llm_async` supports context_tag.
            # I should update `call_llm` (sync) to support context_tag?
            # Or just update the async calls.
            # `_run_jury_evaluation` is SYNC method.
            
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
                from worker.tool_invoker import call_tool
                # Execute sync tool in thread pool
                loop = asyncio.get_running_loop()
                verify_result = await loop.run_in_executor(None, call_tool, tool_name, params)
                
                # Construct verification prompt via PromptService
                db = SessionLocal()
                try:
                    comp_template = PromptService.get_prompt(db, "neutral.verification_comparison")
                    if not comp_template:
                        comp_template = "請比較：\n原：{original_result_preview}\n新：{verify_result_preview}\nJSON: {{consistent: bool}}"
                finally:
                    db.close()

                comparison_prompt = comp_template.format(
                    tool_name=tool_name,
                    params=params,
                    provider_side=provider_side,
                    original_result_preview=str(original_result)[:1000],
                    verify_result_preview=str(verify_result)[:1000]
                )

                # Call LLM for judgement
                judge_response = await call_llm_async(comparison_prompt, system_prompt="你是公正的數據核實員。", context_tag=f"{self.debate_id}:{agent.name}:Verification")
                
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
        db = SessionLocal()
        try:
            final_template = PromptService.get_prompt(db, "neutral.verification_speech")
            if not final_template:
                final_template = "你是中立方。請根據核實報告發言：{verification_report}"
        finally:
            db.close()

        final_prompt = final_template.format(
            agent_name=agent.name,
            round_num=round_num,
            verification_report=verification_report
        )
        
        response = await call_llm_async(final_prompt, system_prompt=f"你是 {agent.name}，公正的第三方。", context_tag=f"{self.debate_id}:{agent.name}:Speech")
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
                 # RAG Recording
                 rag = ReMeHistoryMemory(self.debate_id)
                 await rag.add_turn_async(item['role'], str(item['content']), round_num)
            
            self.history.append({"role": f"{team_name} Summary", "content": team_summary})
            self.full_history.append({"role": f"{team_name} Summary", "content": team_summary})
            
            rag = ReMeHistoryMemory(self.debate_id)
            await rag.add_turn_async(f"{team_name} Summary", team_summary, round_num)
            
        # [Hippocampus] Trigger Memory Consolidation
        self._publish_log("System", "🧠 正在進行海馬體記憶鞏固 (Consolidating Working Memory)...")
        await self.hippocampus.consolidate()

        # [Hippocampus] Trigger Memory Consolidation
        self._publish_log("System", "🧠 正在進行海馬體記憶鞏固 (Consolidating Working Memory)...")
        await self.hippocampus.consolidate()

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
            sys_template = PromptService.get_prompt(db, "debate.team_summary_system")
            if not sys_template: sys_template = "Summarize team discussion."
            system_prompt = sys_template.format(team_name=team_name)

            user_template = PromptService.get_prompt(db, "debate.team_summary_user")
            if not user_template: user_template = "{discussion_text}"
            user_prompt = user_template.format(discussion_text=discussion_text)
        finally:
            db.close()
            
        return await call_llm_async(user_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:TeamSummary:{team_name}")

    def _agent_select_tools(self, agent: AgentBase, side: str):
         """Sync wrapper for backward compatibility"""
         return asyncio.run(self._agent_select_tools_async(agent, side))

    async def _agent_select_tools_async(self, agent: AgentBase, side: str):
        """
        Agent 在辯論開始前動態選擇最適合的工具 (Async).
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
            sys_template = PromptService.get_prompt(db, "debate.tool_selection_system")
            if not sys_template: sys_template = "You are {agent_name}."
            system_prompt = sys_template.format(agent_name=agent.name, side=side, topic=self.topic)

            user_template = PromptService.get_prompt(db, "debate.tool_selection_user")
            if not user_template: user_template = "Select tools: {tools_list_text}"
            user_prompt = user_template.format(tools_list_text=tools_list_text)
        finally:
            db.close()

        try:
            # Async LLM Call
            response = await call_llm_async(user_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}:ToolSelection")
            
            # 嘗試解析 JSON (支援 List 或 Dict 格式)
            selected_tools = []
            
            # 1. Try List [...]
            list_match = re.search(r'\[.*\]', response, re.DOTALL)
            if list_match:
                try:
                    selected_tools = json.loads(list_match.group(0))
                except:
                    pass

            # 2. Try Dict {"tools": [...]} if list failed
            if not selected_tools:
                dict_match = re.search(r'\{.*\}', response, re.DOTALL)
                if dict_match:
                    try:
                        data = json.loads(dict_match.group(0))
                        if isinstance(data, dict):
                            selected_tools = data.get("tools") or data.get("tool_names") or []
                    except:
                        pass
            
            if selected_tools and isinstance(selected_tools, list):
                self.agent_tools_map[agent.name] = selected_tools
                print(f"Agent {agent.name} selected tools: {selected_tools}")
                
                # 格式化工具列表顯示
                tools_display = "\n".join([f"  • {tool}" for tool in selected_tools])
                self._publish_log(f"{agent.name} (Setup)", f"✅ 已選擇 {len(selected_tools)} 個工具：\n{tools_display}")
            else:
                # Fallback: Auto-equip all available tools if selection fails
                all_available = [t['name'] for t in available_tools_list]
                self.agent_tools_map[agent.name] = all_available
                print(f"Agent {agent.name} failed to select tools. Auto-equipping all: {all_available}")
                
                tools_display = "\n".join([f"  • {tool}" for tool in all_available])
                self._publish_log(f"{agent.name} (Setup)", f"⚠️ 工具選擇失敗，已自動裝備所有可用工具 ({len(all_available)}個)：\n{tools_display}")
        except Exception as e:
            print(f"Error in tool selection for {agent.name}: {e}")
            self.agent_tools_map[agent.name] = []
            self._publish_log(f"{agent.name} (Setup)", f"❌ 工具選擇錯誤: {str(e)}")

    def _summarize_old_turns(self):
        """
        分層摘要 (Hierarchical Summarization)：
        將舊的對話歷史進行結構化摘要，保留每個角色的核心觀點。
        """
        keep_recent = 5 # 保留最近 5 條 (增加上下文)
        
        if len(self.history) <= keep_recent + 2:
            return

        # 提取需要壓縮的舊訊息
        to_compress = self.history[:-keep_recent]
        # 更新 self.history，只保留最近的訊息
        self.history = self.history[-keep_recent:]
        
        # 構建待摘要文本
        conversation_text = ""
        for item in to_compress:
            role = item.get('role')
            content = str(item.get('content'))
            if len(content) > 500:
                content = content[:500] + "..."
            conversation_text += f"[{role}]: {content}\n\n"
        
        db = SessionLocal()
        try:
            template = PromptService.get_prompt(db, "debate.hierarchical_summarizer")
            if not template: template = "Summarize: {conversation_text}"
            system_prompt = template
            user_prompt = f"請摘要以下對話：\n\n{conversation_text}"
        finally:
            db.close()
        
        try:
            summary = call_llm(user_prompt, system_prompt=system_prompt)
            if summary:
                self.archived_summaries.append(summary)
                print(f"DEBUG: Hierarchical summary generated. Length: {len(summary)}")
                self._publish_log("System", "已對舊的辯論歷史進行分層摘要處理。")
        except Exception as e:
            print(f"WARNING: Hierarchical summarization failed: {e}")
            # Fallback: Just append raw text truncated if summary fails?
            # Or just keep it in history? No, that would lose data or explode context.
            # Let's append a placeholder.
            self.archived_summaries.append(f"(摘要失敗: {str(e)})")

    def _get_compact_history(self, max_length=2000) -> str:
        """
        獲取優化後的辯論歷史 (Hierarchical Summary + Recent History)
        """
        # 1. 嘗試觸發摘要
        self._summarize_old_turns()
        
        # 2. 組合歷史
        # A. 結構化摘要區
        archived_text = "【過往辯論摘要】\n" + "\n".join(self.archived_summaries)
        
        # B. 近期對話區
        active_history_text = "【近期對話】\n"
        for item in self.history:
            content = item.get("content", "")
            if len(content) > 800:
                content = content[:300] + "...(略)..." + content[-300:]
            active_history_text += f"{item.get('role')}: {content}\n\n"
        
        return f"{archived_text}\n\n{active_history_text}"

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
        # Dynamically fetch available groups from registry for the hint
        available_groups = set()
        for _, t_data in tool_registry.list().items():
             available_groups.add(t_data.get('group', 'basic'))
        groups_str = " | ".join([f"'{g}'" for g in sorted(available_groups)])
        
        tools_desc += f"\n\n### reset_equipped_tools\nDescription: 動態切換工具組 (active tool group)。若你找不到需要的工具，請嘗試切換。\nParameters: {{'group': {groups_str}}}"
        
        # Append Chairman Intervention Tool (Virtual)
        tools_desc += "\n\n### call_chairman\nDescription: 當你發現辯題資訊嚴重不足（如缺乏背景、定義不清），無法進行有效分析時，請使用此工具通知主席介入處理。\nParameters: {'reason': '說明具體缺少什麼資訊或背景'}"

        tools_examples = get_tools_examples() # Examples 暫時保持全集，或者也可以過濾
        
        # Retrieve Tool LTM hints
        tool_hints = ""
        tool_mem = ReMeToolLongTermMemory()
        tool_hints = await tool_mem.retrieve_async(self.topic) # Use topic as context for now
        if tool_hints:
            tools_examples += f"\n\n**過往成功工具調用參考 (ReMe Tool LTM)**:\n{tool_hints}"

        # Retrieve RAG Context (Relevant History)
        rag_context = ""
        rag = ReMeHistoryMemory(self.debate_id)
        # Use current agent role and topic as query
        query = f"{agent.name} {side} {self.topic}"
        relevant_turns = await rag.retrieve_async(query, top_k=2)
        if relevant_turns:
            rag_context = "\n".join([f"> [{t['role']} (Round {t['round']})]: {str(t['content'])[:200]}..." for t in relevant_turns])

        history_text = self._get_compact_history()
        if rag_context:
            history_text += f"\n\n【相關歷史回顧 (RAG)】\n{rag_context}"
        
        db = SessionLocal()
        try:
            # 1. System Prompt Construction
            # Strategy: Combine Agent's Custom Persona with System's Operational Rules
            
            # A. Operational Rules (Externalized)
            operational_rules = PromptService.get_prompt(db, "debater.operational_rules")
            if not operational_rules: operational_rules = "System Rules: Use tools first."
            
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
            system_prompt = default_system
            
            # 2. User Prompt (Tool Instruction)
            user_template = PromptService.get_prompt(db, "debater.tool_instruction")
            if not user_template: user_template = "Instructions: {history_text} {tools_desc}"
            
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
        
        # === Multi-Step Tool Execution Loop ===
        base_max_steps = int(os.getenv("MAX_AGENT_TOOL_STEPS", 5))
        extension_steps = int(os.getenv("EXTENSION_STEPS", 3))
        max_steps = base_max_steps
        has_extended = False
        
        current_step = 0
        current_prompt = user_prompt
        collected_evidence = [] # Track evidence for fallback report
        
        while True: # Outer Loop for Extension Retry
            while current_step < max_steps:
                current_step += 1
                
                # Async LLM Call
                response = await call_llm_async(current_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}")
                print(f"DEBUG: Agent {agent.name} response (Step {current_step}): {response[:500]}")

                # Retry 機制 (Only for empty response on first step)
                if not response and current_step == 1:
                    print(f"WARNING: Empty response from {agent.name}, retrying with simple prompt...")
                    retry_prompt = f"請針對辯題「{self.topic}」發表你的{side}論點。請務必使用繁體中文。"
                    response = await call_llm_async(retry_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}")
                
                # Check for tool call
                try:
                    # 嘗試提取 JSON
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if not json_match:
                        # No JSON found -> Assume final speech -> Return
                        return response
                    
                    json_str = json_match.group(0)
                    try:
                        tool_call = json.loads(json_str)
                    except json.JSONDecodeError:
                        # JSON parse failed -> Treat as text
                        return response

                    # Check if valid tool call
                    if isinstance(tool_call, dict) and "tool" in tool_call and "params" in tool_call:
                        tool_name = str(tool_call["tool"]).strip()
                        params = tool_call["params"]
                        
                        # --- Meta-Tool: reset_equipped_tools ---
                        if tool_name == "reset_equipped_tools":
                            target_group = params.get("group", "basic")
                            print(f"⚙️ Agent {agent.name} is resetting equipped tools to group: {target_group}")
                            self._publish_log(f"{agent.name} (Meta-Tool)", f"Resetting tools to group: {target_group}")
                            
                            group_tools = tool_registry.list(groups=[target_group])
                            self.agent_tools_map[agent.name] = list(group_tools.keys())
                            
                            # Recursive retry with new tools (Reset steps)
                            return await self._agent_turn_async(agent, side, round_num)

                        # --- Meta-Tool: call_chairman (Intervention) ---
                        if tool_name == "call_chairman":
                            reason = params.get("reason", "未說明原因")
                            print(f"🚨 Agent {agent.name} is calling Chairman for help: {reason}")
                            self._publish_log(f"{agent.name} (SOS)", f"請求主席介入：{reason}")

                            chairman_prompt = f"Agent {agent.name} ({side}方) 在分析辯題「{self.topic}」時遇到困難。\n回報原因：{reason}\n請根據你的賽前分析手卡，提供引導。"
                            clarification = await call_llm_async(chairman_prompt, system_prompt="你是辯論主席。請協助遇到困難的辯手。")
                            
                            self._publish_log("Chairman (Intervention)", f"主席回應：{clarification}")
                            
                            intervention_msg = {"role": "Chairman (Intervention)", "content": f"補充說明：\n{clarification}\n請繼續分析。"}
                            self.history.append(intervention_msg)
                            
                            # Recursive retry (Reset steps)
                            return await self._agent_turn_async(agent, side, round_num)

                        # --- Meta-Tool: request_extension (Early access check) ---
                        if tool_name == "request_extension":
                             print(f"Agent {agent.name} requested extension prematurely.")
                             self._publish_log(f"{agent.name} (System)", "⚠️ 你還有剩餘的調查次數，請優先使用工具進行調查。")
                             current_prompt = "系統提示：你還有剩餘的調查次數，無需申請延長。請繼續使用工具搜尋數據。"
                             continue
                        
                        # --- Memory Tool Context Injection ---
                        if tool_name == "search_shared_memory":
                            params["debate_id"] = self.debate_id

                        # --- Regular Tool Execution ---
                        
                        # [STRICT TOOL VALIDATION]
                        # Check if the tool is in the equipped list for this agent
                        equipped_tools = self.agent_tools_map.get(agent.name, [])
                        if tool_name not in equipped_tools:
                            # Bypass validation for special meta-tools if needed, but currently only reset_equipped_tools/call_chairman are meta-tools handled above.
                            # So this block is for regular tools.
                            print(f"❌ Blocked: Agent {agent.name} tried to call unequipped tool: {tool_name}")
                            
                            error_msg = f"Error: Tool '{tool_name}' is not in your equipped list. You can only use: {equipped_tools}. Use 'reset_equipped_tools' if you need to switch toolsets."
                            
                            # Log failure
                            self._publish_log(f"{agent.name} (System)", f"⛔ 拒絕執行：工具 {tool_name} 未裝備")
                            
                            # Append to evidence for context
                            collected_evidence.append(f"【系統錯誤】調用失敗：{error_msg}")
                            
                            # Return error to LLM to correct itself
                            current_prompt = f"系統錯誤：{error_msg}\n請重新選擇有效的工具或發表言論。"
                            continue

                        print(f"✓ Agent {agent.name} calling {tool_name}")
                        self._publish_log(f"{agent.name} (Tool)", f"Calling {tool_name} with {params}")
                        
                        try:
                            # 1. Check Working Memory (Sensory Gating)
                            cached_result = await self.hippocampus.retrieve_working_memory(tool_name, params)
                            
                            if cached_result:
                                tool_result = cached_result['result']
                                self._publish_log(f"{agent.name} (Memory)", f"🧠 從海馬體短期記憶中獲取了結果 (Access: {cached_result['access_count']})")
                            else:
                                # 2. Execute Tool (Sensory Input)
                                from worker.tool_invoker import call_tool
                                loop = asyncio.get_running_loop()
                                tool_result = await loop.run_in_executor(None, call_tool, tool_name, params)
                                
                                # 3. Store in Working Memory
                                await self.hippocampus.store(agent.name, tool_name, params, tool_result)
                                self._publish_log(f"{agent.name} (Tool)", f"工具 {tool_name} 執行成功並存入海馬體。")
                            
                            # Publish Tool Result Preview to Log Stream
                            result_preview_log = str(tool_result)
                            if len(result_preview_log) > 500:
                                result_preview_log = result_preview_log[:500] + "... (點擊查看完整數據)"
                            self._publish_log(f"{agent.name} (Tool Result)", f"📊 工具執行結果摘要：\n{result_preview_log}")
                            
                            # Print full result to backend console for debugging (as requested)
                            print(f"DEBUG: Full tool result for {tool_name}:\n{json.dumps(tool_result, ensure_ascii=False, indent=2, default=str)}")

                            # Record successful tool usage to Tool LTM
                            try:
                                tool_mem = ReMeToolLongTermMemory()
                                await tool_mem.record_async(
                                    intent=f"Debate on {self.topic}",
                                    tool_name=tool_name,
                                    params=params,
                                    result=tool_result,
                                    success=True
                                )
                            except Exception as e:
                                print(f"Warning: Failed to record tool usage to LTM: {e}")

                            # Record Evidence
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
                            
                            # Add to local collection (Truncated for summary)
                            # Avoid huge context overhead
                            result_str = str(tool_result)
                            if len(result_str) > 200:
                                preview = result_str[:200] + "... (完整內容已存檔)"
                            else:
                                preview = result_str
                                
                            collected_evidence.append(f"【證據 {current_step}】{tool_name}\n結果摘要: {preview}")

                        except Exception as e:
                            error_msg = str(e)
                            
                            # --- Tool Name Correction Logic ---
                            if "not found" in error_msg or "Tool" in error_msg:
                                all_tools = list(tool_registry.list().keys())
                                matches = []
                                
                                # 1. Fuzzy Match (Original)
                                fuzzy = difflib.get_close_matches(tool_name, all_tools, n=3, cutoff=0.4)
                                matches.extend(fuzzy)
                                
                                # 2. Case-Insensitive Substring Match (New)
                                tool_name_lower = tool_name.lower()
                                for t in all_tools:
                                    if tool_name_lower in t.lower() or t.lower() in tool_name_lower:
                                        if t not in matches:
                                            matches.append(t)
                                            
                                # 3. Limit suggestions
                                matches = matches[:5]
                                
                                if matches:
                                    suggestion = f" Did you mean: {', '.join(matches)}?"
                                    error_msg += suggestion
                                else:
                                    # If absolutely no match, list all tools in current group if possible, or top 5 generic
                                    error_msg += f" Available tools: {', '.join(all_tools[:5])}..."
                            # ----------------------------------
                            
                            tool_result = {"error": f"Tool execution error: {error_msg}"}
                            print(f"ERROR: Tool {tool_name} failed: {error_msg}")

                            # Record failed tool usage
                            try:
                                tool_mem = ReMeToolLongTermMemory()
                                await tool_mem.record_async(
                                    intent=f"Debate on {self.topic}",
                                    tool_name=tool_name,
                                    params=params,
                                    result=str(e),
                                    success=False
                                )
                            except Exception as ex:
                                print(f"Warning: Failed to record tool failure to LTM: {ex}")

                            collected_evidence.append(f"【證據 {current_step}】{tool_name}\n執行失敗: {error_msg}")
                        
                        # Update prompt with tool result for NEXT step
                        current_prompt = f"""工具 {tool_name} 的執行結果：
{json.dumps(tool_result, ensure_ascii=False, indent=2)}

請根據這些證據進行發言。如果你覺得證據不足，可以再次調用其他工具（請繼續輸出 JSON）。
如果證據足夠，請輸出最終論點（純文字）。"""
                        
                        # Loop continues to next step...
                        continue

                    # Handle Error JSON
                    elif isinstance(tool_call, dict) and "error" in tool_call:
                        # ... (Existing error handling logic) ...
                        # For brevity, if error JSON, we treat as text or retry logic (omitted complex retry for now to fit structure)
                        # Let's just return it or basic text to avoid stuck loop
                        return str(tool_call)
                    
                    else:
                        # JSON found but not a tool call -> Treat as text response
                        return response

                except Exception as e:
                    print(f"Error in agent loop: {e}")
                    return response
            
            # --- Loop Limit Reached ---
            # Allow one-time extension request
            if not has_extended:
                print(f"INFO: Agent {agent.name} reached base limit. Offering extension.")
                self._publish_log(f"{agent.name} (System)", "⚠️ 基礎調查次數已用盡。正在詢問是否需要延長調查...")
                
                # Externalized Prompt
                db = SessionLocal()
                try:
                    ext_template = PromptService.get_prompt(db, "debate.extension_option")
                    if not ext_template: ext_template = "Max steps reached. 1. Conclude. 2. Extend."
                    extension_option_prompt = ext_template.format(base_max_steps=base_max_steps, extension_steps=extension_steps)
                finally:
                    db.close()

                # Ask Agent
                decision_response = await call_llm_async(extension_option_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}")
                
                # Check for extension request
                json_match = re.search(r'\{.*\}', decision_response, re.DOTALL)
                if json_match:
                    try:
                        req = json.loads(json_match.group(0))
                        if req.get("tool") == "request_extension":
                            reason = req.get("params", {}).get("reason", "無理由")
                            self._publish_log(f"{agent.name} (Request)", f"申請延長調查：{reason}")
                            
                            # [Hippocampus] Check Shared Memory before bothering Chairman
                            self._publish_log("System", f"🧠 正在查詢海馬體記憶以驗證延長需求...")
                            mem_results = await self.hippocampus.search_shared_memory(query=reason, limit=3)
                            
                            # Heuristic: If "No relevant memories" is NOT in the result, it means we found something.
                            # Ideally search_shared_memory should return a list or structured object, but it returns a string currently.
                            # We can check if the result string length implies found content.
                            
                            if "No relevant memories" not in mem_results and len(mem_results) > 50:
                                self._publish_log("System", f"✅ 海馬體中發現相關資訊，延長申請自動駁回並提供資訊。")
                                current_prompt = f"【系統提示】延長申請已自動駁回，因為在共享記憶中發現了相關資訊：\n\n{mem_results}\n\n請利用這些資訊繼續你的論述或總結。"
                                continue # Back to agent loop
                            
                            # Call Chairman for Review
                            db = SessionLocal()
                            try:
                                review_template = PromptService.get_prompt(db, "debate.chairman_review_extension")
                                # If template not found (e.g. not init yet), use fallback
                                if not review_template:
                                    review_template = """
你是主席。Agent {agent_name} 申請延長調查。
理由：{reason}
證據摘要：{evidence_summary}
請回傳 JSON: {{"approved": true/false, "reason": "...", "guidance": "..."}}
"""
                                chairman_sys = review_template.format(
                                    agent_name=agent.name, 
                                    side=side, 
                                    topic=self.topic, 
                                    reason=reason,
                                    evidence_summary="\n".join(collected_evidence)[-1000:] # Last 1000 chars
                                )
                            finally:
                                db.close()
                                
                            chairman_res = await call_llm_async("請進行審核。", system_prompt=chairman_sys, context_tag=f"{self.debate_id}:Chairman")
                            
                            # Parse Chairman Decision
                            try:
                                res_json = json.loads(re.search(r'\{.*\}', chairman_res, re.DOTALL).group(0))
                                if res_json.get("approved"):
                                    max_steps += extension_steps
                                    has_extended = True
                                    self._publish_log("Chairman (Review)", f"✅ 批准延長：{res_json.get('reason')}")
                                    
                                    # Update prompt with guidance
                                    current_prompt = f"主席已批准延長調查。\n指導：{res_json.get('guidance')}\n請繼續你的調查或發言。"
                                    continue # Continue Outer Loop (re-enters Inner Loop with higher max_steps)
                                else:
                                    self._publish_log("Chairman (Review)", f"❌ 拒絕延長：{res_json.get('reason')}")
                                    current_prompt = f"主席拒絕了你的申請。\n理由：{res_json.get('reason')}\n請立即根據現有資訊發表總結。"
                                    # Fall through to forced summary (or return text if agent replies text next time)
                                    # Actually, we should force summary NOW or give one last chance?
                                    # Let's give one last chance with text-only constraint.
                                    final_res = await call_llm_async(current_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}")
                                    return final_res
                                    
                            except Exception as e:
                                print(f"Error parsing chairman review: {e}")
                                # Fallback: Deny
                    except:
                        pass
                
                # If not extension request or denied/failed, return the response as text (if it's text)
                # or fallback report if it's still JSON but not extension
                if not json_match:
                    return decision_response
            
            # If reached here, it means extension denied or invalid request, break outer loop to fallback
            break
        
        # Loop ended (either max steps reached again, or denied extension)
        # FORCE A CONCLUSION: Instead of returning a system report, force the LLM to speak based on whatever it has.
        print(f"WARNING: Agent {agent.name} reached max steps ({max_steps}). Forcing conclusion.")
        
        evidence_text = "\n\n".join(collected_evidence)
        self._publish_log(f"{agent.name} (System)", f"⚠️ 調用次數耗盡，正在強制生成總結發言...")
        
        force_conclusion_prompt = f"""
【系統強制指令】
你已經達到工具調用次數上限，不能再使用工具了。
請根據你目前已蒐集到的證據（或若無證據，則根據你的專業知識與邏輯推演），立即發表你的本輪論點。

**已蒐集的證據摘要**：
{evidence_text}

請直接輸出你的辯論發言（純文字）：
"""
        try:
            # Force call without tool capability (modify system prompt? No, just strong instruction)
            # We use the same system prompt but a very strong user instruction.
            final_speech = await call_llm_async(force_conclusion_prompt, system_prompt=system_prompt, context_tag=f"{self.debate_id}:{agent.name}")
            return final_speech
        except Exception as e:
             # If even this fails, then fallback to report
             print(f"Error in forced conclusion: {e}")
             return f"(系統報告：Agent 在強制總結時發生錯誤，證據如下)\n{evidence_text}"
