from typing import List, Dict, Any
from worker.chairman import Chairman
from worker.guardrail_agent import GuardrailAgent
from agentscope.agent import AgentBase
import json
import re
import os
import sys
import yaml
import asyncio
import resource
import difflib
from datetime import datetime, timezone, timedelta
from worker.llm_utils import call_llm, call_llm_async
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
import hashlib
from worker.memory import ReMePersonalLongTermMemory, ReMeTaskLongTermMemory, ReMeToolLongTermMemory, ReMeHistoryMemory, HippocampalMemory
from api.tool_registry import tool_registry
from api.toolset_service import ToolSetService
from api.redis_client import get_redis_client
from api import models
from mars.types.errors import ToolError, ToolRecoverableError, ToolTerminalError, ToolFatalError, TejErrorType

class DebateCycle:
    """
    管理整个辩论循环，包括主席引导、正反方发言和总结。
    """

    def __init__(self, debate_id: str, topic: str, chairman: Chairman, teams: List[Dict], rounds: int, enable_cross_examination: bool = True):
        self.debate_id = debate_id
        self.topic = topic
        self.chairman = chairman
        self.teams = teams # List of dicts: [{"name": "...", "side": "...", "agents": [AgentBase...]}]
        self.rounds = rounds
        self.enable_cross_examination = enable_cross_examination
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
        self.latest_db_date = None # [Phase 18] Date Awareness Handshake
        
        # [Optimization] Persistent LTM instances for buffering
        self.history_memory = ReMeHistoryMemory(debate_id)
        self.tool_memory = ReMeToolLongTermMemory()
        
        # [Robustness] Failure Mode Memory
        # Key: f"{agent_name}:{tool_name}:{error_type}" -> Value: {count, last_params_hash}
        self._failure_memory: Dict[str, Dict[str, Any]] = {}
        
        # [Observability] Loop Sentinel
        self._loop_sentinel: Dict[str, int] = {} # Key: signature -> count
        
        # Log de-duplication cache: key -> {"last_ts": datetime, "suppressed": int}
        self._log_dedupe: Dict[str, Dict[str, Any]] = {}
        
        # [Debug] Setup debug log directory
        self.debug_log_enabled = os.getenv("DEBUG_LOG_ENABLE", "false").lower() == "true"
        if self.debug_log_enabled:
            self.debug_log_dir = "debate_logs"
            os.makedirs(self.debug_log_dir, exist_ok=True)
            # [Realtime] Stream log file
            self.stream_log_path = os.path.join(self.debug_log_dir, f"stream_{self.debate_id}.log")
            self._log_to_file(f"=== Debate Stream Started: {self.debate_id} ===")
        
        # [Debug] Full Execution Trace
        self.debug_trace: List[Dict[str, Any]] = []
        
        # [Observability Phase 6] Tool Stats
        self.tool_stats = {
            "count": 0,
            "total_time": 0.0,
            "estimated_cost": 0.0
        }
        
        # [Governance] Guardrail Agent
        self.guardrail_agent = GuardrailAgent()

    def _log_to_file(self, message: str):
        """Append message to the realtime stream log."""
        if not self.debug_log_enabled or not hasattr(self, 'stream_log_path'):
            return
        try:
            with open(self.stream_log_path, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Failed to write to stream log: {e}")

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
        具備去重與節流：
        - 同一 role+content 在 1 秒內重複，將被抑制並累計 suppressed 計數。
        - 下一次允許的輸出會附帶 "(previous N duplicates suppressed)" 註記。
        """
        # Ensure timestamp is Asia/Taipei (GMT+8)
        tz_taipei = timezone(timedelta(hours=8))
        now = datetime.now(timezone.utc).astimezone(tz_taipei)
        timestamp = now.strftime("%H:%M:%S")

        # De-duplication key
        key = f"{role}|{content}"
        entry = self._log_dedupe.get(key)
        allow_publish = True
        suppressed_note = ""
        dedupe_window_seconds = 1.0

        if entry:
            last_ts = entry.get("last_ts")
            suppressed = entry.get("suppressed", 0)
            # If within the dedupe window, suppress
            if last_ts and (now - last_ts).total_seconds() < dedupe_window_seconds:
                entry["suppressed"] = suppressed + 1
                entry["last_ts"] = now
                self._log_dedupe[key] = entry
                allow_publish = False
            else:
                # Outside the window: if there were suppressed duplicates, annotate once
                if suppressed:
                    suppressed_note = f" (previous {suppressed} duplicates suppressed)"
                # Reset counter and publish
                entry["suppressed"] = 0
                entry["last_ts"] = now
                self._log_dedupe[key] = entry
        else:
            # First time seeing this message
            self._log_dedupe[key] = {"last_ts": now, "suppressed": 0}

        if not allow_publish:
            return
        
        # Add timestamp to console log
        print(f"[{timestamp}] {role}: {content[:100]}...{suppressed_note}")
        
        # [Realtime] Log to file
        self._log_to_file(f"[{role}] {content}{suppressed_note}")
        
        # Add timestamp to UI content
        ui_content = f"[{timestamp}] {content}{suppressed_note}"
        
        message = json.dumps({"role": role, "content": ui_content}, ensure_ascii=False)
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", message)
        # Persist log for late-joiners
        self.redis_client.rpush(f"debate:{self.debate_id}:log_history", message)

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

    def _save_round_debug_log(self, round_num: int, team_summaries: Dict[str, str]):
        """
        Save detailed debug log for the current round (Appended to single file).
        """
        if not self.debug_log_enabled:
            return

        try:
            # Use single file for the whole debate
            filename = f"debate_debug_{self.debate_id}.txt"
            filepath = os.path.join(self.debug_log_dir, filename)
            
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"=== 第 {round_num} 輪除錯日誌 (Round {round_num} Debug Log) ===\n")
                f.write(f"{'='*60}\n")
                f.write(f"Debate ID: {self.debate_id}\n")
                f.write(f"Topic: {self.topic}\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("--- 各團隊總結 (Team Summaries) ---\n")
                for team, summary in team_summaries.items():
                    f.write(f"[{team}]:\n{summary}\n\n")
                
                f.write("\n--- 近期對話歷史 (Detailed History - Recent) ---\n")
                for item in self.history[-50:]: # Last 50 items
                    f.write(f"[{item.get('role')}]: {str(item.get('content'))[:500]}...\n")
                
                f.write("\n--- 完整執行追蹤：LLM 輸入輸出與工具結果 (Full Execution Trace) ---\n")
                
                for i, trace in enumerate(self.debug_trace):
                    f.write(f"\n[Trace #{i+1}] {trace.get('timestamp')}\n")
                    f.write(f"Agent: {trace.get('agent')}\n")
                    f.write(f"Step: {trace.get('step')}\n")
                    f.write(f"Event: {trace.get('event')}\n")
                    
                    if "prompt" in trace:
                        f.write(f"Full Prompt:\n{trace['prompt']}\n")
                    if "response" in trace:
                        f.write(f"LLM Response: {trace['response']}\n")
                    if "tool" in trace:
                        f.write(f"Tool Call: {trace['tool']} params={trace.get('params')}\n")
                    if "result" in trace:
                        # Full Result
                        try:
                            res_str = json.dumps(trace['result'], ensure_ascii=False, indent=2, default=str)
                        except:
                            res_str = str(trace['result'])
                        f.write(f"Tool Result: {res_str}\n")
                    f.write("-" * 40 + "\n")

                f.write("\n--- 前端與系統日誌串流 (Frontend & System Logs) ---\n")
                try:
                    # Fetch all logs from Redis
                    redis_logs = self.redis_client.lrange(f"debate:{self.debate_id}:log_history", 0, -1)
                    for log_json in redis_logs:
                        try:
                            entry = json.loads(log_json)
                            f.write(f"[{entry.get('role')}]: {entry.get('content')}\n")
                        except:
                            f.write(f"[Raw]: {log_json}\n")
                except Exception as e:
                    f.write(f"[Error fetching system logs]: {e}\n")

            print(f"[Debug] Round {round_num} log saved to {filepath}")
        except Exception as e:
            print(f"[Debug] Failed to save debug log: {e}")

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
        
        # 0.5 [Phase 18] Database Handshake (Date Awareness)
        self._publish_progress(8, "正在檢測資料庫最新日期...", "init")
        await self._check_db_date_async()

        # 0. 賽前分析
        # [Phase 18] Database Handshake
        await self._check_db_date_async()

        # Check Task LTM for similar past debates
        # [OPTIONAL] Disabled to avoid cold-start issues if not required
        # task_mem = ReMeTaskLongTermMemory()
        # similar_tasks = await task_mem.retrieve_similar_tasks_async(self.topic)
        # if similar_tasks:
        #     print(f"DEBUG: Found similar past debates:\n{similar_tasks}")
        #     self._publish_log("System", f"Found similar past debates:\n{similar_tasks}")

        self._publish_progress(10, "主席正在進行賽前分析...", "analysis")
        
        # Chairman analysis is now fully async
        self.analysis_result = await self.chairman.pre_debate_analysis(self.topic, debate_id=self.debate_id)
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
            
            # [Phase 18] Chairman Emergency Mode (After Round 1)
            if i == 1:
                await self._check_and_trigger_emergency_mode(round_result)
        
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

        # [Duration Stats]
        total_duration = datetime.now() - start_time
        duration_msg = f"🏁 辯論結束。總耗時: {str(total_duration).split('.')[0]}"
        
        # [Phase 6] Cache Stats & Metrics
        cache_stats = self.hippocampus.stats
        total_reqs = cache_stats['wm_hits'] + cache_stats['wm_misses']
        hit_rate = (cache_stats['wm_hits'] / total_reqs * 100) if total_reqs > 0 else 0
        
        # Semantic Cache Stats
        from worker.llm_utils import _semantic_cache_buffer
        sem_hits = _semantic_cache_buffer.stats["hits"]
        sem_misses = _semantic_cache_buffer.stats["misses"]
        sem_total = sem_hits + sem_misses
        sem_hit_rate = (sem_hits / sem_total * 100) if sem_total > 0 else 0
        
        avg_latency = (self.tool_stats["total_time"] / self.tool_stats["count"]) if self.tool_stats["count"] > 0 else 0
        
        stats_msg = f"📊 Cache Stats: WM Hit {hit_rate:.1f}% | Sem Hit {sem_hit_rate:.1f}% | Saved Calls: {cache_stats['wm_hits'] + sem_hits}"
        perf_msg = f"⚡ Perf: Avg Tool Latency {avg_latency:.2f}s | Est Cost: ${self.tool_stats['estimated_cost']:.2f}"
        
        detailed_stats = {
            "hippocampus_hit_rate": hit_rate,
            "semantic_cache_hit_rate": sem_hit_rate,
            "api_calls_saved": cache_stats['wm_hits'] + sem_hits,
            "total_api_cost": self.tool_stats["estimated_cost"],
            "qdrant_writes": cache_stats['ltm_writes'],
            "avg_tool_latency": avg_latency
        }
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {duration_msg}")
        print(f"DEBUG: FINAL METRICS: {json.dumps(detailed_stats, indent=2)}")
        
        self._publish_log("System", duration_msg)
        self._publish_log("System", stats_msg)
        self._publish_log("System", perf_msg)

        # Send explicit DONE signal to close the stream
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", "[DONE]")
        
        return {
            "topic": self.topic,
            "rounds_data": self.rounds_data,
            "analysis": self.analysis_result,
            "final_conclusion": final_conclusion,
            "jury_report": jury_report
        }

    async def _check_db_date_async(self):
        """
        [Phase 18] Handshake with DB to find the latest available date.
        Uses TSMC (2330.TW) as a canary to probe database freshness.
        """
        try:
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            
            # Probe recent 60 days
            today = datetime.now()
            start_date = (today - timedelta(days=60)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            
            params = {
                "coid": "2330.TW",
                "mdate.gte": start_date,
                "mdate.lte": end_date,
                # Fetch all in range to find max date manually (safer than relying on sort param support)
            }
            
            self._publish_log("System", f"🔍 正在檢測資料庫最新日期 (Probe: 2330.TW)...")
            
            result = await loop.run_in_executor(None, call_tool, "tej.stock_price", params)
            
            found_date = None
            if isinstance(result, dict):
                 data = result.get("data") or result.get("results")
                 if isinstance(data, list) and data:
                     # Find max date
                     dates = []
                     for row in data:
                         d = row.get("mdate")
                         if d:
                             dates.append(str(d).split("T")[0])
                     
                     if dates:
                         found_date = max(dates)
            
            # [Fix] Fallback Probe with Multi-Step Query (Chunking)
            # If recent data missing, look back iteratively in 90-day chunks up to 1 year
            if not found_date:
                self._publish_log("System", "⚠️ 無近期數據，啟動長週期回溯搜索 (Multi-Step Probe)...")
                
                # Try up to 4 quarters back (approx 1 year)
                for i in range(1, 5):
                    # Calculate chunk window (shifting back 90 days each time)
                    # Window: [Today - 90*(i+1), Today - 90*i]
                    # But we want continuous coverage backward.
                    # Previous probe was [Today-60, Today]
                    # Let's do strictly 90-day chunks backward from Today-60
                    
                    chunk_end_dt = today - timedelta(days=60 + (i-1)*90)
                    chunk_start_dt = chunk_end_dt - timedelta(days=90)
                    
                    chunk_start = chunk_start_dt.strftime("%Y-%m-%d")
                    chunk_end = chunk_end_dt.strftime("%Y-%m-%d")
                    
                    self._publish_log("System", f"🔍 回溯探測 ({i}/4): {chunk_start} ~ {chunk_end}")
                    
                    params_chunk = {
                        "coid": "2330.TW",
                        "mdate.gte": chunk_start,
                        "mdate.lte": chunk_end,
                        "opts.limit": 100,
                        "sort": "mdate.desc"
                    }
                    
                    try:
                        result_chunk = await loop.run_in_executor(None, call_tool, "tej.stock_price", params_chunk)
                        if isinstance(result_chunk, dict):
                             data = result_chunk.get("data") or result_chunk.get("results")
                             if isinstance(data, list) and data:
                                 dates = []
                                 for row in data:
                                     d = row.get("mdate")
                                     if d:
                                         dates.append(str(d).split("T")[0])
                                 if dates:
                                     found_date = max(dates)
                                     self._publish_log("System", f"✅ 在回溯中找到數據: {found_date}")
                                     break # Found it, stop looking back
                    except Exception as ex:
                        print(f"Probe chunk failed: {ex}")
                        continue

            if found_date:
                self.latest_db_date = found_date
                self._publish_log("System", f"📅 資料庫最新數據日期確認: {self.latest_db_date}")
            else:
                self._publish_log("System", f"⚠️ 無法確認資料庫日期 (兩次探測皆失敗)。")
                # Fallback: Don't set a fake date, just leave as None.
                self.latest_db_date = None

        except Exception as e:
            print(f"DB Handshake Failed: {e}")
            self._publish_log("System", f"⚠️ 資料庫連線檢查失敗: {e}")

    async def _check_and_trigger_emergency_mode(self, round_result: Dict):
        """
        [Phase 18] Chairman Emergency Research Mode.
        Checks if Round 1 was full of "Insufficient Data" claims.
        """
        team_summaries = round_result.get("team_summaries", {})
        combined_text = " ".join(team_summaries.values())
        
        # Heuristic: Detect keywords implying lack of data
        # Note: Agents might hallucinate, so we also check if Evidence logs were empty?
        # But we only have text summaries here easily.
        # Let's check for specific keywords we injected or standard complaints.
        triggers = ["資料不足", "無法獲取數據", "無數據", "Insufficient Data", "empty result"]
        hit_count = sum(1 for t in triggers if t in combined_text)
        
        if hit_count >= 1: # Low threshold for safety, or check evidence_log directly
            # Check redis evidence for emptiness/errors
            # Implementation detail: fetch recent evidence
            pass # Keep it simple for now based on text
            
            self._publish_log("Chairman", "🚨 偵測到資料嚴重不足 (Emergency Mode Triggered)。主席介入調查...")

            # 1. Force enable 'searxng.search' for all agents
            enabled_count = 0
            for agent_name, tools in self.agent_tools_map.items():
                if "searxng.search" not in tools:
                    tools.append("searxng.search")
                    self.agent_tools_map[agent_name] = tools
                    enabled_count += 1
            
            if enabled_count > 0:
                self._publish_log("System", f"🔧 已強制為 {enabled_count} 位 Agent 開啟外部搜尋工具 (searxng.search)。")

            # 2. Chairman performs web search
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            
            search_q = f"{self.topic} news analysis stock price reasons"
            search_res = await loop.run_in_executor(None, call_tool, "searxng.search", {"q": search_q})
            
            context_inject = f"【主席緊急補充資訊】\n由於內部資料庫回應有限，主席提供了外部搜尋結果：\n{str(search_res)[:800]}..."
            
            # Inject into History so all agents see it next
            self.history.append({"role": "Chairman (Intervention)", "content": context_inject})
            self.full_history.append({"role": "Chairman (Intervention)", "content": context_inject})
            
            # Also push to Memory
            await self.history_memory.add_turn_async("Chairman (Intervention)", context_inject, 1)

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
        
        # [Governance] Check against Verified Set
        verified_set = self.redis_client.smembers(f"debate:{self.debate_id}:verified_evidence")
        # Redis client returns strings directly due to decode_responses=True
        verified_set = verified_set if verified_set else set()
        
        target_evidence = []
        for e in all_evidence:
            if e.get('side') == 'neutral': continue
            
            # Robust Signature check
            ev_sig = f"{e.get('timestamp')}-{e.get('tool')}"
            if ev_sig in verified_set: continue
            
            target_evidence.append(e)
        
        verification_report = ""
        
        if not target_evidence:
            return await self._agent_turn_async(agent, 'neutral', round_num) # Fallback to normal turn if no evidence

        # 2. Verify each evidence (Limit to 1-2 to save time/cost)
        # Sort by importance? For now, FIFO from the list we filtered.
        for i, ev in enumerate(target_evidence[:2]):
            tool_name = ev.get('tool')
            params = ev.get('params')
            original_result = ev.get('result')
            provider_side = ev.get('side', 'Unknown')
            provider_agent = ev.get('agent_name', 'Unknown')
            
            self._publish_log(f"{agent.name} (Verification)", f"正在核實 {provider_side} 方 ({provider_agent}) 使用的工具: {tool_name}...")
            
            try:
                # Re-execute tool (Upgrade: Use Verified Price for stock/index tools)
                from worker.tool_invoker import call_tool
                loop = asyncio.get_running_loop()
                
                # [Governance] Neutral should use the Auditor Tool for price verification
                # Check ALL price-related tools
                price_tools = ["tej.stock_price", "yahoo.stock_price", "twse.stock_day", "financial.get_verified_price"]
                verify_result = None
                is_auditor_check = False
                
                if tool_name in price_tools:
                    # Extract symbol/date from params
                    # Different tools have different param names, so we normalize here
                    v_symbol = params.get("coid") or params.get("symbol")
                    # Try to find a date
                    v_date = params.get("mdate.gte") or params.get("start_date") or params.get("date")
                    
                    if v_symbol and v_date:
                        self._publish_log(f"{agent.name} (Verification)", f"⚡ 切換至審計工具 (financial.get_verified_price) 進行交叉驗證...")
                        # Use Auditor Tool
                        # [Fix] Ensure date format is YYYYMMDD for TWSE (financial.get_verified_price)
                        # v_date usually comes as YYYY-MM-DD from TEJ params.
                        clean_date = str(v_date)[:10].replace("-", "")
                        verify_result = await loop.run_in_executor(None, call_tool, "financial.get_verified_price", {"symbol": v_symbol, "date": clean_date})
                        is_auditor_check = True
                
                # If not price tool or param extraction failed, fall back to exact re-execution
                if verify_result is None:
                    # Regular re-execution for other tools (Bypass Cache)
                    params_bypass = params.copy()
                    params_bypass["_bypass_cache"] = True
                    verify_result = await loop.run_in_executor(None, call_tool, tool_name, params_bypass)

                # --- Programmatic Pre-Check ---
                # Check for "Empty vs Non-Empty" discrepancy specifically for Auditor Checks
                programmatic_fail = False
                fail_reason = ""
                
                if is_auditor_check:
                    # Original result empty?
                    orig_empty = False
                    if isinstance(original_result, dict) and (not original_result.get("data") and not original_result.get("results")):
                        orig_empty = True
                    elif isinstance(original_result, list) and not original_result:
                        orig_empty = True
                        
                    # Verify result empty?
                    verify_empty = False
                    if isinstance(verify_result, dict) and (not verify_result.get("data") and not verify_result.get("results")):
                        verify_empty = True
                    elif isinstance(verify_result, list) and not verify_result:
                        verify_empty = True
                        
                    # Case: Agent claimed data but Auditor says empty (Hallucination of Data Existence?)
                    # OR: Agent said empty but Auditor found data (Laziness?) -> Less severe
                    # Most severe: Agent output fabricated numbers (not easy to check programmatically without parsing numbers)
                    pass

                # Construct verification prompt via PromptService
                db = SessionLocal()
                try:
                    comp_template = PromptService.get_prompt(db, "neutral.verification_comparison")
                    if not comp_template:
                        comp_template = """
請擔任「數據核實員」，比較兩份工具執行結果並判斷是否一致。

【工具資訊】
工具：{tool_name}
參數：{params}
來源：{provider_side} ({provider_agent})

【原執行結果 (Original)】
{original_result_preview}

【核實執行結果 (Auditor Verification)】
{verify_result_preview}

【判斷標準】
1. **數據一致性**: 數值是否大致相同？（允許微小誤差）
2. **無中生有 (Hallucination)**: 若原結果有數據，但核實結果為「空 (Empty/No Data)」，則視為嚴重違規（編造數據）。
3. **格式差異**: 若僅是格式不同但內容實質相同，視為一致。

請輸出 JSON 格式：
{{
    "consistent": true/false,
    "score_penalty": 0 到 -10 (若嚴重違規請扣分),
    "comment": "簡短評語"
}}
"""
                finally:
                    db.close()

                comparison_prompt = comp_template.format(
                    tool_name=tool_name,
                    params=params,
                    provider_side=provider_side,
                    provider_agent=provider_agent,
                    original_result_preview=str(original_result)[:1500],
                    verify_result_preview=str(verify_result)[:1500]
                )

                # Call LLM for judgement
                judge_response = await call_llm_async(comparison_prompt, system_prompt="你是公正的數據核實員。請嚴格揪出編造數據的行為。", context_tag=f"{self.debate_id}:{agent.name}:Verification")
                
                # Parse JSON
                try:
                    # Robust JSON extraction
                    json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
                    if json_match:
                        judge_json = json.loads(json_match.group(0))
                        
                        consistent = judge_json.get('consistent', True)
                        penalty = judge_json.get('score_penalty', 0)
                        comment = judge_json.get('comment', '')
                        
                        # [Governance] Apply specific penalties for Hallucination
                        if not consistent:
                             # Ensure negative
                             if penalty > 0: penalty = -penalty
                             if penalty == 0: penalty = -5 # Default penalty
                        
                        if consistent:
                            verification_report += f"- ✅ 核實通過 ({tool_name}): 數據一致。\n"
                        else:
                            verification_report += f"- ❌ 核實失敗 ({tool_name}): {comment} (扣分: {penalty})\n"
                            if penalty < 0:
                                self._update_team_score(provider_side, float(penalty), f"證據核實失敗 ({provider_agent}): {comment}")
                    else:
                        verification_report += f"- ⚠️ 無法判斷 ({tool_name}): {judge_response[:50]}...\n"

                except Exception as e:
                    print(f"Verification judgment parsing error: {e}")
                    verification_report += f"- ⚠️ 核實判讀錯誤 ({tool_name})\n"
                
                # [Optimization] Mark evidence as verified in Redis
                ev_sig = f"{ev.get('timestamp')}-{tool_name}"
                self.redis_client.sadd(f"debate:{self.debate_id}:verified_evidence", ev_sig)

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

    async def _run_cross_examination_async(self, round_num: int, team_summaries: Dict[str, str]):
        """
        執行交叉質詢環節 (Async)。
        """
        # 簡單策略：Pro 質詢 Con，然後 Con 質詢 Pro
        # 如果有 Neutral，則 Neutral 可以質詢雙方
        
        # Identify teams
        pro_team = next((t for t in self.teams if t.get('side') == 'pro'), None)
        con_team = next((t for t in self.teams if t.get('side') == 'con'), None)
        
        if not pro_team or not con_team:
            return

        pairs = [
            (pro_team, con_team), # Pro asks Con
            (con_team, pro_team)  # Con asks Pro
        ]
        
        for attacker, defender in pairs:
            attacker_name = attacker['name']
            defender_name = defender['name']
            defender_summary = team_summaries.get(defender_name, "")
            
            # Select representative agent (e.g., first one)
            attacker_agent = attacker['agents'][0]
            defender_agent = defender['agents'][0]
            
            # 1. Attacker Generates Question
            self._publish_log(attacker_name, f"正在構思對 {defender_name} 的質詢問題...")
            
            db = SessionLocal()
            try:
                q_template = PromptService.get_prompt(db, "debate.cross_exam_question")
                if not q_template: q_template = "基於對方的論點：{opponent_summary}，請提出一個犀利的反駁問題。"
            finally:
                db.close()
                
            q_prompt = q_template.format(opponent_summary=defender_summary)
            question = await call_llm_async(q_prompt, system_prompt=f"你是 {attacker_name} 的辯手。", context_tag=f"{self.debate_id}:CrossExam:Q:{attacker_name}")
            
            self._publish_log(f"{attacker_name} (Q)", f"❓ 質詢：{question}")
            self.history.append({"role": f"{attacker_name} (Cross-Exam Q)", "content": question})
            self.full_history.append({"role": f"{attacker_name} (Cross-Exam Q)", "content": question})
            
            # 2. Defender Answers
            self._publish_log(defender_name, f"正在思考如何回答 {attacker_name} 的質詢...")
            
            db = SessionLocal()
            try:
                a_template = PromptService.get_prompt(db, "debate.cross_exam_answer")
                if not a_template: a_template = "對方問題：{question}。請根據我方立場進行反駁與回答。"
            finally:
                db.close()
                
            a_prompt = a_template.format(question=question)
            answer = await call_llm_async(a_prompt, system_prompt=f"你是 {defender_name} 的辯手。", context_tag=f"{self.debate_id}:CrossExam:A:{defender_name}")
            
            self._publish_log(f"{defender_name} (A)", f"💡 回答：{answer}")
            self.history.append({"role": f"{defender_name} (Cross-Exam A)", "content": answer})
            self.full_history.append({"role": f"{defender_name} (Cross-Exam A)", "content": answer})

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
                 # RAG Recording (Buffered via self.history_memory)
                 await self.history_memory.add_turn_async(item['role'], str(item['content']), round_num)
            
            self.history.append({"role": f"{team_name} Summary", "content": team_summary})
            self.full_history.append({"role": f"{team_name} Summary", "content": team_summary})
            
            await self.history_memory.add_turn_async(f"{team_name} Summary", team_summary, round_num)
            
        # [Hippocampus] Trigger Memory Consolidation
        self._publish_log("System", "🧠 正在進行海馬迴記憶鞏固 (Consolidating Working Memory)...")
        await self.hippocampus.consolidate()
        
        # [Optimization] Flush LTM buffers
        self._publish_log("System", "💾 正在同步長期記憶 (Flushing LTM Buffers)...")
        await self.history_memory.flush()
        await self.tool_memory.flush()
        
        # [Phase 18] Chairman Emergency Mode Check (After Round 1)
        if round_num == 1:
            await self._check_and_trigger_emergency_mode(round_team_summaries)

        # 2.5 交叉質詢 (Cross-Examination)
        if self.enable_cross_examination:
            self._publish_log("Chairman", f"進入第 {round_num} 輪交叉質詢環節 (Cross-Examination)...")
            await self._run_cross_examination_async(round_num, round_team_summaries)

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
        
        # [Debug] Save Round Log
        self._save_round_debug_log(round_num, round_team_summaries)
        
        return {
            "round": round_num,
            "team_summaries": round_team_summaries,
            "next_direction": next_direction
        }
        
    async def _check_and_trigger_emergency_mode(self, summaries: Dict[str, str]):
        """
        Check if agents are failing to get data and trigger emergency web search.
        """
        # Heuristic: If summaries contain keywords like "no data", "empty", "lack of evidence"
        failure_signals = ["no data", "empty", "lack of evidence", "查無資料", "數據不足", "無法驗證"]
        combined_text = " ".join(summaries.values()).lower()
        
        score = sum(1 for s in failure_signals if s in combined_text)
        
        if score >= 2: # Threshold
            self._publish_log("Chairman (Emergency)", "🚨 偵測到多方數據不足。主席啟動「緊急研究模式 (Emergency Research Mode)」！")
            self._publish_log("System", "🔓 強制解鎖 Web Search 工具給所有 Agent...")
            
            # Force enable search tools for everyone
            # This is a bit hacky, we assume agents can use 'searxng.search' if we tell them,
            # or we need to update tool_registry?
            # Actually, agents select tools at start. We can't easily inject new tools into their `agent_tools_map` unless we update it.
            
            for agent_name in self.agent_tools_map:
                if "searxng.search" not in self.agent_tools_map[agent_name]:
                    self.agent_tools_map[agent_name].append("searxng.search")
                    
            # Inject a system note into history
            msg = "【主席指令】鑑於內部數據庫資料不足，現已開放網絡搜索權限。請善用 `searxng.search` 查找外部新聞與報告來補充論點。"
            self.history.append({"role": "Chairman (System)", "content": msg})
            self.full_history.append({"role": "Chairman (System)", "content": msg})

    async def _check_and_trigger_emergency_mode(self, round_result: Dict):
        """
        Check if agents are failing to get data and trigger emergency web search.
        """
        # Heuristic: If summaries contain keywords like "no data", "empty", "lack of evidence"
        team_summaries = round_result.get("team_summaries", {})
        combined_text = " ".join(team_summaries.values()).lower()
        
        failure_signals = ["no data", "empty", "lack of evidence", "查無資料", "數據不足", "無法驗證"]
        score = sum(1 for s in failure_signals if s in combined_text)
        
        if score >= 2: # Threshold
            self._publish_log("Chairman (Emergency)", "🚨 偵測到多方數據不足。主席啟動「緊急研究模式 (Emergency Research Mode)」！")
            self._publish_log("System", "🔓 強制解鎖 Web Search 工具給所有 Agent...")
            
            # Force enable search tools for everyone
            for agent_name in self.agent_tools_map:
                if "searxng.search" not in self.agent_tools_map[agent_name]:
                    self.agent_tools_map[agent_name].append("searxng.search")
                    
            # Inject a system note into history
            msg = "【主席指令】鑑於內部數據庫資料不足，現已開放網絡搜索權限。請善用 `searxng.search` 查找外部新聞與報告來補充論點。"
            self.history.append({"role": "Chairman (System)", "content": msg})
            self.full_history.append({"role": "Chairman (System)", "content": msg})

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

            # [Optimization Phase 7] Role-Based Tool Suggestion
            # Sort/Tag tools based on agent side
            sorted_tools = []
            
            # Define priority sets
            # [Phase 1 Update] Hide raw 'tej.stock_price' to force use of 'financial.get_verified_price'
            # We filter OUT tej.stock_price from the suggestion list, but keep other tej tools (like financial_summary)
            tej_tools = [t for t in available_tools_list if "tej" in t['name'] and t['name'] != "tej.stock_price"]
            
            # 'financial.get_verified_price' is in official_tools
            official_tools = [t for t in available_tools_list if "twse" in t['name'] or "verified" in t['name']]
            backup_tools = [t for t in available_tools_list if "yahoo" in t['name'] or "search" in t['name']]
            other_tools = [t for t in available_tools_list if t not in tej_tools and t not in official_tools and t not in backup_tools and t['name'] != "tej.stock_price"]
            
            if side in ["pro", "con"]:
                # Pro/Con prioritize Verified Price (High Precision + Fallback)
                # Highlight verified tools
                # [Priority Adjustment] TWSE/Official tools first due to TEJ lag
                sorted_tools.extend([{"name": t['name'], "description": f"[推薦:2025最新數據/官方驗證] {t['description']}"} for t in official_tools])
                sorted_tools.extend(tej_tools) # Other TEJ tools
                sorted_tools.extend(backup_tools)
                sorted_tools.extend(other_tools)
            elif side == "neutral":
                # Neutral prioritize Official/Verified (Audit)
                sorted_tools.extend([{"name": t['name'], "description": f"[推薦:官方驗證] {t['description']}"} for t in official_tools])
                sorted_tools.extend(tej_tools)
                sorted_tools.extend(backup_tools)
                sorted_tools.extend(other_tools)
            else:
                # Default mix
                sorted_tools = []
                # Ensure verified price is visible/prioritized even in default
                sorted_tools.extend(official_tools)
                sorted_tools.extend(tej_tools)
                sorted_tools.extend(backup_tools)
                sorted_tools.extend(other_tools)

            tools_list_text = "\n".join([f"- {t['name']}: {t['description']}" for t in sorted_tools])
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
            
            # [Fix Phase 21] Robust JSON Parsing
            # 1. Clean Markdown code blocks ```json ... ```
            cleaned_response = re.sub(r'```json\s*(.*?)\s*```', r'\1', response, flags=re.DOTALL)
            cleaned_response = re.sub(r'```\s*(.*?)\s*```', r'\1', cleaned_response, flags=re.DOTALL)
            
            # 2. Try List [...]
            list_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if list_match:
                try:
                    selected_tools = json.loads(list_match.group(0))
                except:
                    pass

            # 3. Try Dict {"tools": [...]} if list failed
            if not selected_tools:
                dict_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
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
                # [Fix Phase 21] Improved Fallback Strategy
                # Fallback: Instead of equipping ALL tools (which explodes context), equip a Safe Default Set
                # Role-based fallback
                if side == "neutral":
                    default_tools = ["financial.get_verified_price", "twse.stock_day", "internal.search_company", "searxng.search"]
                else:
                    # Pro/Con: Add fallbacks (TWSE/Yahoo) to default set
                    # [Phase 1 Update] Replace 'tej.stock_price' with 'financial.get_verified_price' in default fallback
                    default_tools = ["financial.get_verified_price", "tej.financial_summary", "internal.search_company", "searxng.search"]
                
                # Filter defaults to ensure they are available to this agent
                available_names = [t['name'] for t in available_tools_list]
                # We need to ensure 'financial.get_verified_price' is in available_tools_list?
                # It should be if it's registered globally or assigned.
                # If not, we might need to add it explicitly to the fallback if we trust it exists.
                safe_fallback = [t for t in default_tools if t in available_names]
                
                # If no safe fallback found (rare), then fall back to all
                if not safe_fallback:
                    safe_fallback = available_names
                
                self.agent_tools_map[agent.name] = safe_fallback
                
                print(f"Agent {agent.name} failed to select tools. Raw response: {response[:100]}... Using fallback: {safe_fallback}")
                
                tools_display = "\n".join([f"  • {tool}" for tool in safe_fallback])
                self._publish_log(f"{agent.name} (Setup)", f"⚠️ 工具選擇解析失敗 (Raw: {response[:50]}...)，已啟用安全預設工具組 ({len(safe_fallback)}個)：\n{tools_display}")

        except Exception as e:
            print(f"Error in tool selection for {agent.name}: {e}")
            # Final Fallback
            self.agent_tools_map[agent.name] = ["searxng.search"]
            self._publish_log(f"{agent.name} (Setup)", f"❌ 工具選擇發生錯誤: {str(e)}。已啟用基礎搜尋工具。")

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
        ollama_tools = []
        
        # 如果有選擇，則只顯示選擇的工具；否則顯示所有「可用」的工具
        if selected_tool_names:
            filtered_tools = {}
            for name in selected_tool_names:
                try:
                    # Using get_tool_data ensures lazy tools are loaded and schema is available
                    # Assuming version 'v1' for now as selection doesn't specify version
                    tool_data = tool_registry.get_tool_data(name)
                    filtered_tools[name] = tool_data
                    
                    # Convert to Ollama tool format
                    # Ensure parameters schema is valid and robust
                    params_schema = tool_data.get('schema')
                    if not params_schema:
                        params_schema = {"type": "object", "properties": {}, "required": []}
                    elif isinstance(params_schema, dict):
                        # Ensure 'type' is object
                        if "type" not in params_schema:
                            params_schema["type"] = "object"
                        # Ensure 'properties' exists
                        if "properties" not in params_schema:
                            params_schema["properties"] = {}
                    
                    # Fix: description might be a dict (metadata) or a string
                    desc = tool_data.get('description', '')
                    if isinstance(desc, dict):
                        desc = desc.get('description', '')

                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": desc,
                            "parameters": params_schema
                        }
                    })
                except Exception as e:
                    print(f"Warning: Selected tool '{name}' not found or failed to load: {e}")

            if not filtered_tools:
                 # 如果選擇無效，回退到顯示該 Agent 所有可用的工具 (ToolSet)
                 tools_desc = get_tools_description()
            else:
                 tools_desc = "你已選擇並激活以下工具（系統已自動掛載）：\n" + "\n".join([f"- {name}: {data['description']}" for name, data in filtered_tools.items()])
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
        # Use persistent instance
        tool_hints = await self.tool_memory.retrieve_async(self.topic) # Use topic as context for now
        if tool_hints:
            tools_examples += f"\n\n**過往成功工具調用參考 (ReMe Tool LTM)**:\n{tool_hints}"

        # Retrieve RAG Context (Relevant History)
        rag_context = ""
        # Use persistent instance
        # Use current agent role and topic as query
        query = f"{agent.name} {side} {self.topic}"
        relevant_turns = await self.history_memory.retrieve_async(query, top_k=2)
        if relevant_turns:
            rag_context = "\n".join([f"> [{t['role']} (Round {t['round']})]: {str(t['content'])[:200]}..." for t in relevant_turns])

        history_text = self._get_compact_history()
        if rag_context:
            history_text += f"\n\n【相關歷史回顧 (RAG)】\n{rag_context}"
        
        db = SessionLocal()
        try:
            # 1. System Prompt Construction
            # [Governance] Use PromptService.compose_system_prompt to inject Base Contract
            
            # A. Prepare Agent Persona
            custom_prompt = getattr(agent, 'system_prompt', '').strip()
            if not custom_prompt:
                custom_prompt = f"你是 {agent.name}，代表 {side} 方。"
            
            # Additional Context
            persona_context = f"""
{custom_prompt}

辯題：{self.topic}
立場：{side}
"""
            # B. Operational Rules (Externalized)
            operational_rules = PromptService.get_prompt(db, "debater.operational_rules")
            if not operational_rules:
                # Minimal fallback if not found
                operational_rules = "System Rules: Use tools first. Do NOT fabricate data."

            # [Phase 18] Dynamic Data Honesty Rules
            if self.latest_db_date:
                operational_rules += f"\nSystem Note: The database data ends on {self.latest_db_date}. Do not query future dates."

            # C. Compose Final System Prompt
            final_persona = f"{persona_context}\n\n# Operational Rules\n{operational_rules}"
            system_prompt = PromptService.compose_system_prompt(db, override_content=final_persona)
            
            # 2. User Prompt (Tool Instruction)
            user_template = PromptService.get_prompt(db, "debater.tool_instruction")
            if not user_template: user_template = "Instructions: {history_text} {tools_desc}"
            
            # [Phase 18] Dynamic Date Injection
            db_date_info = ""
            if self.latest_db_date:
                db_date_info = f"\n**注意：資料庫最新數據日期為 {self.latest_db_date}。**"
            
            # [Fix] Stronger instruction for Fallback
            fallback_hint = """

💡 **重要提示 (Fallback Strategy)**：
1. **數據獲取優先級**: `twse.stock_day` (首選, 2025年最新數據) -> `tej.stock_price` (備用, 歷史回測) -> `yahoo.stock_price` (最後手段)。
2. **遇到空數據時**: 若 `tej` 回傳空列表 `[]`，這通常是因為資料庫尚未更新至 2025 年。請立即改用 `twse.stock_day` 查詢最新數據。
3. **搜尋關鍵字優化**: 若需使用 `searxng` 查找財報或新聞，**請勿僅搜尋代碼**。
   - ❌ 避免: `"2330"`
   - ✅ 推薦: `"2330.TW 2024 Q4 營收 YoY"` 或 `"台積電 法說會 重點"`
"""
            
            user_prompt = user_template.format(
                round_num=round_num,
                history_text=history_text,
                chairman_summary=self.analysis_result.get('step5_summary', '無'),
                current_date=f"{CURRENT_DATE} {db_date_info}",
                stock_codes=chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                tools_desc=tools_desc,
                tools_examples=tools_examples + fallback_hint
            )
        finally:
            db.close()
        
        # === Multi-Step Tool Execution Loop ===
        base_max_steps = int(os.getenv("MAX_AGENT_TOOL_STEPS", 5))
        extension_steps = int(os.getenv("EXTENSION_STEPS", 3))
        max_steps = base_max_steps
        extensions_used = 0
        last_extension_reason = ""
        
        current_step = 0
        current_prompt = user_prompt
        collected_evidence = [] # Track evidence for fallback report
        tool_call_history = [] # Track last N tool calls to prevent loops (A-B-A patterns)
        
        # [Governance] Retry Loop Context
        guardrail_retries = 0
        MAX_GUARDRAIL_RETRIES = 2
        
        while True: # Outer Loop for Extension Retry
            while current_step < max_steps:
                current_step += 1
                
                # Async LLM Call (Passing tools!)
                response = await call_llm_async(
                    current_prompt,
                    system_prompt=system_prompt,
                    context_tag=f"{self.debate_id}:{agent.name}",
                    tools=ollama_tools if ollama_tools else None
                )
                print(f"DEBUG: Agent {agent.name} response (Step {current_step}): {response[:500]}")
                
                # [Debug] Trace LLM IO
                trace_item = {
                    "timestamp": datetime.now().isoformat(),
                    "agent": agent.name,
                    "step": current_step,
                    "event": "LLM_RESPONSE",
                    "prompt": current_prompt,
                    "response": response
                }
                self.debug_trace.append(trace_item)
                
                # [Realtime] Log trace details
                self._log_to_file(f"--- [LLM IO] {agent.name} Step {current_step} ---\nPrompt Preview: {current_prompt[:200]}...\nResponse Preview: {response[:200]}...")

                # --- [Governance] Guardrail Check ---
                # Check ALL text responses, and potentially Tool Calls (if we want to block dangerous tools)
                # Here we check Text Responses (non-tool calls) primarily to stop Hallucination/Scope Creep
                is_tool_call = False
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        tool_call_test = json.loads(json_match.group(0))
                        if isinstance(tool_call_test, dict) and "tool" in tool_call_test:
                            is_tool_call = True
                    except:
                        pass
                
                # Guardrail Logic: Intercept final speech or reasoning steps
                if not is_tool_call:
                    check_context = f"Topic: {self.topic}\nLast Evidence: {str(collected_evidence[-1]) if collected_evidence else 'None'}"
                    audit_result = self.guardrail_agent.check(agent.name, response, check_context)
                    
                    if audit_result["status"] == "REJECTED":
                        self._publish_log("Guardrail", f"⛔ 攔截違規發言 ({audit_result['violation_type']}): {audit_result['reason']}")
                        
                        if guardrail_retries < MAX_GUARDRAIL_RETRIES:
                            guardrail_retries += 1
                            current_prompt = f"【Guardrail 合規警告】\n你的回答被拒絕，原因：{audit_result['reason']}。\n修正指令：{audit_result['correction_instruction']}\n\n請根據指令修正後重新輸出。"
                            
                            # Log Audit Event
                            self.redis_client.publish("guardrail:audit", json.dumps({
                                "debate_id": self.debate_id,
                                "agent": agent.name,
                                "action": "REJECTED",
                                "reason": audit_result["reason"]
                            }, ensure_ascii=False))
                            
                            # Decrease step count to not penalize retry? Or consume step?
                            # Design: Consume step to force convergence.
                            continue
                        else:
                            self._publish_log("Guardrail", f"⚠️ 重試次數過多，強制放行 (標記為風險內容)。")
                            # Force Pass but Log Warning
                            # (Proceed as normal)
                    elif audit_result["status"] == "WARNING":
                         self._publish_log("Guardrail", f"⚠️ 合規警告: {audit_result['reason']}")

                # ------------------------------------

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
                        
                        # --- Check for Duplicate Call (Loop Prevention & Sentinel) ---
                        current_call_signature = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
                        
                        # [Robustness] Enhanced Loop Detection (History Check)
                        # Check against ALL previous calls in this turn to prevent ANY exact repeats
                        if current_call_signature in tool_call_history:
                            print(f"⚠️ Loop detected: Agent {agent.name} repeated call {tool_name}")
                            self._publish_log(f"{agent.name} (System)", f"⚠️ 偵測到重複調用 ({tool_name})，已攔截。")
                            current_prompt = f"系統提示：你在本回合已經執行過這個工具（參數相同）。請不要重複調用。請嘗試修改參數（如日期範圍）、更換工具，或直接根據現有資訊進行分析。"
                            
                            # [Observability] Log Metric
                            print(f"[LOOP_DETECTED] agent={agent.name} tool={tool_name} type=history_repeat")
                            continue
                        
                        tool_call_history.append(current_call_signature)
                        
                        # Soft loop check (frequency)
                        sentinel_key = f"{agent.name}:{current_call_signature}"
                        self._loop_sentinel[sentinel_key] = self._loop_sentinel.get(sentinel_key, 0) + 1
                        if self._loop_sentinel[sentinel_key] > 2:
                             print(f"[LOOP_DETECTED] agent={agent.name} tool={tool_name} type=frequent_access count={self._loop_sentinel[sentinel_key]}")
                        # --------------------------------------------------

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

                            # [Loop Fix] Auto-Equip Tools on "Missing Data" complaints
                            # If reason contains "lack", "missing", "data", "price", "stock" -> try to equip fallback tools
                            triggers = ["缺", "miss", "data", "數據", "資料", "price", "stock", "股價", "2480"]
                            if any(t in reason.lower() for t in triggers):
                                fallback_tools = ["financial.get_verified_price", "tej.stock_price", "yahoo.stock_price"]
                                added_tools = []
                                current_tools = self.agent_tools_map.get(agent.name, [])
                                
                                for ft in fallback_tools:
                                    if ft not in current_tools:
                                        current_tools.append(ft)
                                        added_tools.append(ft)
                                
                                if added_tools:
                                    self.agent_tools_map[agent.name] = current_tools
                                    self._publish_log("System", f"🛠️ [Auto-Fix] 偵測到 Agent 缺少數據工具，已自動為 {agent.name} 裝備：{', '.join(added_tools)}")

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
                                
                                # [Memory Opt] Mark as Adopted since we are using it
                                await self.hippocampus.mark_adopted(tool_name, params)
                                
                                # Create a preview string for debugging
                                try:
                                    result_str = json.dumps(tool_result, ensure_ascii=False)
                                except:
                                    result_str = str(tool_result)
                                # Show FULL content for debugging as requested
                                self._publish_log(f"{agent.name} (Memory)", f"🧠 從海馬迴短期記憶中獲取了結果 (Access: {cached_result['access_count']}) 『{result_str}』")
                            else:
                                # 2. Execute Tool (Sensory Input)
                                from worker.tool_invoker import call_tool
                                loop = asyncio.get_running_loop()
                                
                                # [Observability] Track Latency & Cost
                                start_tool = datetime.now()
                                tool_result = await loop.run_in_executor(None, call_tool, tool_name, params)
                                tool_duration = (datetime.now() - start_tool).total_seconds()
                                
                                self.tool_stats["count"] += 1
                                self.tool_stats["total_time"] += tool_duration
                                
                                # Simple Cost Model
                                cost = 0.0
                                if tool_name.startswith("tej."): cost = 0.03 # $0.03 per TEJ call
                                elif tool_name.startswith("searxng."): cost = 0.00 # Free
                                elif tool_name.startswith("financial."): cost = 0.01 # Auditor
                                self.tool_stats["estimated_cost"] += cost
                                
                                # 3. Store in Working Memory
                                await self.hippocampus.store(agent.name, tool_name, params, tool_result)
                                self._publish_log(f"{agent.name} (Tool)", f"工具 {tool_name} 執行成功並存入海馬迴。")
                            
                            # Publish Tool Result Preview to Log Stream
                            result_preview_log = str(tool_result)
                            if len(result_preview_log) > 500:
                                result_preview_log = result_preview_log[:500] + "... (點擊查看完整數據)"
                            self._publish_log(f"{agent.name} (Tool Result)", f"📊 工具執行結果摘要：\n{result_preview_log}")
                            
                            # Print full result to backend console for debugging (as requested)
                            print(f"DEBUG: Full tool result for {tool_name}:\n{json.dumps(tool_result, ensure_ascii=False, indent=2, default=str)}")
                            
                            # [Debug] Trace Tool Result
                            self.debug_trace.append({
                                "timestamp": datetime.now().isoformat(),
                                "agent": agent.name,
                                "step": current_step,
                                "event": "TOOL_RESULT",
                                "tool": tool_name,
                                "params": params,
                                "result": tool_result
                            })
                            
                            # [Realtime] Log trace details
                            self._log_to_file(f"--- [TOOL RESULT] {agent.name} ---\nTool: {tool_name}\nParams: {params}\nResult Preview: {str(tool_result)[:200]}...")

                            # Record successful tool usage to Tool LTM
                            try:
                                # Use persistent instance
                                await self.tool_memory.record_async(
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
                            
                            # [Optimization Phase 18] Data Honesty Check
                            # Check if result is effectively empty
                            is_empty_result = False
                            if isinstance(tool_result, dict):
                                # TEJ standard: {'data': [], ...} or {'results': []}
                                if not tool_result.get("data") and not tool_result.get("results") and not tool_result.get("content"):
                                     # Check specific keys that might contain data
                                     if "data" in tool_result or "results" in tool_result:
                                         is_empty_result = True
                            elif isinstance(tool_result, list) and len(tool_result) == 0:
                                is_empty_result = True
                            
                            # Add to local collection (Truncated for summary)
                            # Avoid huge context overhead
                            result_str = str(tool_result)
                            if len(result_str) > 200:
                                preview = result_str[:200] + "... (完整內容已存檔)"
                            else:
                                preview = result_str
                                
                            collected_evidence.append(f"【證據 {current_step}】{tool_name}\n結果摘要: {preview}")
                            
                            # Prepare prompt for next step
                            next_prompt_suffix = ""
                            if is_empty_result:
                                next_prompt_suffix = "\n\n⚠️ **系統警告 (Data Honesty)**：此工具調用返回了 **空數據 (Empty)**。\n這意味著 TEJ 數據庫中可能沒有這段期間的資料。\n\n**請立即執行 Fallback 策略**：\n1. 若你是查詢股價，請改用 `twse.stock_day` (參數: symbol, date) 或 `yahoo.stock_price`。\n2. 若你是查詢財務數據，請嘗試調整日期範圍或改用 `searxng.search` 查找新聞報導。\n3. **絕對禁止**編造數據。"

                        except Exception as e:
                            # [Error Taxonomy & Failure Mode Handling]
                            error_msg = str(e)
                            is_fatal = False
                            advice = ""
                            
                            # Check for Structured ToolError
                            if isinstance(e, ToolError):
                                error_type = e.error_type
                                meta = e.metadata
                                
                                # Failure Mode Memory Check
                                # Hash params to detect "same error + same params"
                                param_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
                                fm_key = f"{agent.name}:{tool_name}:{error_type.value}"
                                
                                if fm_key not in self._failure_memory:
                                    self._failure_memory[fm_key] = {"count": 0, "hashes": set()}
                                
                                self._failure_memory[fm_key]["count"] += 1
                                self._failure_memory[fm_key]["hashes"].add(param_hash)
                                
                                # Circuit Breaker logic
                                if self._failure_memory[fm_key]["count"] > 3:
                                    advice += "\n\n⚠️ 系統警告：你已連續多次遭遇此類型錯誤。請停止嘗試此路徑，改用其他分析方法。"
                                
                                if error_type == TejErrorType.RECOVERABLE:
                                    advice = f"\n💡 建議調整參數：{meta.get('hint', '請檢查參數格式')}。"
                                    if "retry_after" in meta:
                                        time.sleep(meta["retry_after"]) # Basic backoff
                                        
                                elif error_type == TejErrorType.TERMINAL:
                                    advice = "\n⛔ 此錯誤為終端錯誤（資料不存在或路徑無效）。請勿再重試此工具/參數組合。"
                                    # We could force stop tool usage here, but prompt guidance is softer first step.
                                    
                                elif error_type == TejErrorType.FATAL:
                                    advice = "\n🔥 嚴重錯誤。請立即停止工具調用，並向主席回報。"
                                    is_fatal = True

                            # --- Tool Name Correction Logic (Legacy Fallback) ---
                            elif "not found" in error_msg or "Tool" in error_msg:
                                all_tools = list(tool_registry.list().keys())
                                matches = []
                                fuzzy = difflib.get_close_matches(tool_name, all_tools, n=3, cutoff=0.4)
                                matches.extend(fuzzy)
                                tool_name_lower = tool_name.lower()
                                for t in all_tools:
                                    if tool_name_lower in t.lower() or t.lower() in tool_name_lower:
                                        if t not in matches: matches.append(t)
                                matches = matches[:5]
                                if matches: error_msg += f" Did you mean: {', '.join(matches)}?"
                                else: error_msg += f" Available tools: {', '.join(all_tools[:5])}..."
                            # ----------------------------------
                            
                            final_msg = f"Tool execution error: {error_msg}{advice}"
                            tool_result = {"error": final_msg}
                            print(f"ERROR: Tool {tool_name} failed: {final_msg}")
                            
                            # [Debug] Trace Tool Failure
                            self.debug_trace.append({
                                "timestamp": datetime.now().isoformat(),
                                "agent": agent.name,
                                "step": current_step,
                                "event": "TOOL_FAILURE",
                                "tool": tool_name,
                                "params": params,
                                "result": tool_result
                            })

                            # Record failed tool usage
                            try:
                                await self.tool_memory.record_async(
                                    intent=f"Debate on {self.topic}",
                                    tool_name=tool_name,
                                    params=params,
                                    result=final_msg,
                                    success=False
                                )
                            except Exception as ex:
                                print(f"Warning: Failed to record tool failure to LTM: {ex}")

                            collected_evidence.append(f"【證據 {current_step}】{tool_name}\n執行失敗: {final_msg}")
                            
                            if is_fatal:
                                # Break inner loop to force conclusion or chairman call
                                current_prompt = f"系統發生嚴重錯誤 ({error_msg})，請立即終止調查並回報。"
                                # Force next step to be text response (conclusion)
                                # But we continue loop to let agent explain.
                        
                        # Update prompt with tool result for NEXT step
                        # Use variable next_prompt_suffix if defined (from Data Honesty Check)
                        if 'next_prompt_suffix' not in locals():
                            next_prompt_suffix = ""

                        current_prompt = f"""工具 {tool_name} 的執行結果：
{json.dumps(tool_result, ensure_ascii=False, indent=2)}

【系統提示】
1. 請檢查上述結果中的 system_hint (若有)。
2. 若獲得了公司 ID/Ticker，請務必繼續調用財務或股價工具 (如 tej.stock_price, tej.financial_summary) 以獲取深度數據。
3. 不要只停留在搜尋結果，請挖掘數據背後的趨勢。
4. 如果證據已足夠支持你的論點，請輸出最終發言（純文字）。{next_prompt_suffix}
"""
                        
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
            # Allow multiple extension requests (Auto-Approve first 2, then Chairman Review)
            # Limit total extensions to prevent infinite loop (e.g., max 3 times total)
            if extensions_used < 3:
                print(f"INFO: Agent {agent.name} reached step limit ({max_steps}). Offering extension ({extensions_used+1}/3).")
                self._publish_log(f"{agent.name} (System)", "⚠️ 調查次數已用盡。正在詢問是否需要延長調查...")
                
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
                            self._publish_log(f"{agent.name} (Request)", f"申請延長調查 ({extensions_used+1}/3)：{reason}")
                            
                            # [Hippocampus] Check Shared Memory first
                            self._publish_log("System", f"🧠 正在查詢海馬迴記憶以驗證延長需求...")
                            mem_results = await self.hippocampus.search_shared_memory(query=reason, limit=3)
                            
                            if "No relevant memories" not in mem_results and len(mem_results) > 50:
                                self._publish_log("System", f"✅ 海馬迴中發現相關資訊，延長申請自動駁回並提供資訊。")
                                current_prompt = f"【系統提示】延長申請已自動駁回，因為在共享記憶中發現了相關資訊：\n\n{mem_results}\n\n請利用這些資訊繼續你的論述或總結。"
                                continue # Back to agent loop
                            
                            # --- [Optimization Phase 1] Auto-Approve Logic ---
                            should_auto_approve = False
                            deny_reason_auto = ""
                            
                            # Only auto-approve first 2 times
                            if extensions_used < 2:
                                # 1. Substantiality Check
                                filler_words = ["need time", "more steps", "process", "thinking", "continue", "investigate", "research"]
                                is_only_filler = any(w in reason.lower() for w in filler_words) and len(reason) < 25
                                has_specifics = any(c.isupper() for c in reason) or any(c.isdigit() for c in reason)
                                
                                # 2. Repetition Check
                                is_repeated = (reason.strip() == last_extension_reason.strip())
                                
                                if len(reason) < 10:
                                    deny_reason_auto = "理由過短"
                                elif is_repeated:
                                    deny_reason_auto = "理由重複"
                                elif is_only_filler and not has_specifics:
                                    deny_reason_auto = "缺乏具體細節 (需包含實體或數據)"
                                else:
                                    should_auto_approve = True
                            
                            if should_auto_approve:
                                self._publish_log("System (Auto-Approve)", f"✅ 系統自動批准延長 (符合自動放行標準)。")
                                max_steps += extension_steps
                                extensions_used += 1
                                last_extension_reason = reason
                                current_prompt = f"系統已自動批准你的延長申請。\n增加了 {extension_steps} 次調用機會。\n請繼續調查。"
                                continue # Back to agent loop
                            
                            if extensions_used < 2 and not should_auto_approve:
                                self._publish_log("System (Auto-Approve)", f"⚠️ 自動批准拒絕 ({deny_reason_auto})，轉交主席審核...")

                            # --- End Auto-Approve ---

                            # Call Chairman for Review (Fallback)
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
                                    extensions_used += 1
                                    last_extension_reason = reason
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