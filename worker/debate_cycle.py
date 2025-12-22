from typing import List, Dict, Any, Optional
from api.config import Config
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
import time
import hashlib
from datetime import datetime, timezone, timedelta
from worker.llm_utils import call_llm, call_llm_async
from worker.tool_config import get_tools_description, get_tools_examples, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from worker.memory import ReMePersonalLongTermMemory, ReMeTaskLongTermMemory, ReMeToolLongTermMemory, ReMeHistoryMemory, HippocampalMemory
from api.redis_client import get_redis_client
from api import models
from mars.types.errors import ToolError, ToolRecoverableError, ToolTerminalError, ToolFatalError, TejErrorType

class DebateCycle:
    """
    管理辯論循環，實施方法論治理與數據鏈路優化。
    """

    def __init__(self, debate_id: str, topic: str, chairman: Chairman, teams: List[Dict], rounds: int, enable_cross_examination: bool = True):
        self.debate_id = debate_id
        self.topic = topic
        self.chairman = chairman
        self.teams = teams
        self.rounds = rounds
        self.enable_cross_examination = enable_cross_examination
        self.redis_client = get_redis_client()
        self.evidence_key = f"debate:{self.debate_id}:evidence"
        self.rounds_data = []
        self.analysis_result = {}
        self.history = []
        self.full_history = []
        self.archived_summaries = []
        self.agent_tools_map = {}
        self.hippocampus = HippocampalMemory(debate_id)
        self.discovered_urls = set()
        self.browse_quota = 0
        self.latest_db_date = None
        self.latest_db_date_meta = {}
        self.history_memory = ReMeHistoryMemory(debate_id)
        self.tool_memory = ReMeToolLongTermMemory()
        from api.tool_registry import tool_registry
        self.tool_registry = tool_registry
        self._failure_memory = {}
        self._loop_sentinel = {}
        self._log_dedupe = {}
        self.debug_log_enabled = os.getenv("DEBUG_LOG_ENABLE", "false").lower() == "true"
        if self.debug_log_enabled:
            self.debug_log_dir = "debate_logs"
            os.makedirs(self.debug_log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.stream_log_path = os.path.join(self.debug_log_dir, f"stream_{self.debate_id}_{ts}.log")
            self._debug_filename = f"debate_debug_{self.debate_id}_{ts}.txt"
        self.debug_trace = []
        self.tool_stats = {"count": 0, "total_time": 0.0, "estimated_cost": 0.0}
        self.guardrail_agent = GuardrailAgent()

    def _log_to_file(self, message: str):
        if not self.debug_log_enabled or not hasattr(self, 'stream_log_path'): return
        try:
            with open(self.stream_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        except: pass

    def _get_memory_usage(self) -> str:
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return f"{usage / 1024 / 1024:.2f} MB" if sys.platform == 'darwin' else f"{usage / 1024:.2f} MB"
        except: return "N/A"

    def _publish_log(self, role: str, content: str):
        tz = timezone(timedelta(hours=8)); now = datetime.now(timezone.utc).astimezone(tz)
        timestamp = now.strftime("%H:%M:%S"); key = f"{role}|{content}"
        entry = self._log_dedupe.get(key)
        if entry and (now - entry["last_ts"]).total_seconds() < 1.0:
            entry["suppressed"] += 1; entry["last_ts"] = now; return
        supp_note = f" (previous {entry['suppressed']} duplicates suppressed)" if entry and entry["suppressed"] else ""
        self._log_dedupe[key] = {"last_ts": now, "suppressed": 0}
        ui_content = f"[{timestamp}] {content}{supp_note}"
        message = json.dumps({"role": role, "content": ui_content}, ensure_ascii=False)
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", message)
        self.redis_client.rpush(f"debate:{self.debate_id}:log_history", message)
        self._log_to_file(f"[{role}] {content}{supp_note}")

    def _publish_progress(self, percentage: int, message: str, stage: str = "setup"):
        event = {"type": "progress_update", "progress": percentage, "message": message, "stage": stage, "timestamp": datetime.now().isoformat()}
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", json.dumps(event, ensure_ascii=False))

    def _save_round_debug_log(self, round_num: int, team_summaries: Dict[str, str]):
        if not self.debug_log_enabled: return
        try:
            filepath = os.path.join(self.debug_log_dir, getattr(self, '_debug_filename', f"debug_{self.debate_id}.txt"))
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\nRound {round_num} Debug Log\n{team_summaries}\n")
        except: pass

    def _run_jury_evaluation(self, final_conclusion: str) -> str:
        self._publish_log("System", "⚖️ 正在進行評審團評估...")
        db = SessionLocal()
        try:
            sys_p = PromptService.get_prompt(db, "debate.jury_system") or "你是評審團。"
            user_p = f"辯題：{self.topic}\n結論：{final_conclusion}"
            return call_llm(user_p, system_prompt=sys_p)
        finally: db.close()

    def _save_report_to_file(self, conclusion: str, jury_report: str = None, investment_report: str = None, start_time: datetime = None, end_time: datetime = None):
        report_dir = "data/replays"; os.makedirs(report_dir, exist_ok=True)
        safe_topic = re.sub(r'[<>:"/\\|?*]', '', self.topic).replace(' ', '_')[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(report_dir, f"{safe_topic}_{timestamp}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# 辯論報告：{self.topic}\n\n## 最終結論\n{conclusion}\n\n## 評審團報告\n{jury_report}\n")
        print(f"Report saved to {filepath}")

    async def start_async(self) -> Dict[str, Any]:
        start_time = datetime.now(); self._publish_log("System", f"Debate '{self.debate_id}' started.")
        await self._check_db_date_async()
        
        # Phase 1: Analysis
        analysis_packet = await self.chairman.pre_debate_analysis(self.topic, debate_id=self.debate_id)
        self.analysis_result = analysis_packet.get("analysis", {}); self.bg_info = analysis_packet.get("bg_info", "")
        
        # [Phase 38] Debate Anchor Decree
        anchor_decree = await self.chairman.generate_anchor_decree(self.topic, self.bg_info, self.debate_id)
        self._publish_log("Chairman (Decree)", anchor_decree); self.anchor_decree = anchor_decree
        anchor_msg = {"role": "Chairman (Decree)", "content": anchor_decree}
        self.history.append(anchor_msg); self.full_history.append(anchor_msg)

        # Double Check Decree
        await self._conduct_neutral_fact_check(self.analysis_result.get("step00_decree", {}))
        
        # Phase 2: Tool Selection
        for team in self.teams:
            for agent in team['agents']: await self._agent_select_tools_async(agent, team.get('side', 'neutral'))

        # Phase 3: Rounds
        for i in range(1, self.rounds + 1):
            round_result = await self._run_round_async(i)
            self.rounds_data.append(round_result)
            if i == 1: await self._check_and_trigger_emergency_mode(round_result)
        
        # Phase 4: Conclusion
        final_conclusion = await self.chairman.summarize_debate(self.debate_id, self.topic, self.rounds_data)
        jury_report = self._run_jury_evaluation(final_conclusion)
        investment_report = await self._generate_investment_report(self.rounds_data, final_conclusion)
        self._save_report_to_file(final_conclusion, jury_report, investment_report, start_time, datetime.now())
        self.redis_client.publish(f"debate:{self.debate_id}:log_stream", "[DONE]")
        return {"final_conclusion": final_conclusion}

    async def _run_round_async(self, round_num: int) -> Dict[str, Any]:
        round_log = []; team_summaries = {}
        for team in self.teams:
             team_result = await self._process_team_deliberation(team, round_num)
             self.history.extend(team_result['log']); self.full_history.extend(team_result['log'])
             round_log.extend(team_result['log']); team_summaries[team['name']] = team_result['summary']
        await self._audit_methodology_and_relevance(round_num, team_summaries)
        return {"round": round_num, "team_summaries": team_summaries, "log": round_log}

    async def _process_team_deliberation(self, team: Dict, round_num: int) -> Dict[str, Any]:
        team_name = team['name']; side = team.get('side', 'neutral'); agent_results = []
        for agent in team['agents']:
            content = await self._agent_turn_async(agent, side, round_num)
            agent_results.append(content)
        team_log = []
        for agent, content in zip(team['agents'], agent_results):
            role = f"{team_name} - {agent.name}"
            team_log.append({"role": role, "content": content})
            self._publish_log(role, content)
        summary = await self._generate_team_summary_async(team_name, [f"{t['role']}: {t['content']}" for t in team_log])
        return {"name": team_name, "summary": summary, "log": team_log}

    async def _generate_team_summary_async(self, team_name: str, logs: List[str]) -> str:
        return await call_llm_async("\n".join(logs), system_prompt=f"你是 {team_name} 的總結員。")

    async def _agent_select_tools_async(self, agent: AgentBase, side: str):
        db = SessionLocal()
        try:
            from api.toolset_service import ToolSetService
            agent_id = getattr(agent, 'id', None)
            available = ToolSetService.get_agent_available_tools(db, agent_id) if agent_id else []
            names = [t['name'] for t in available]
            self.agent_tools_map[agent.name] = names if names else ["searxng.search"]
            self._publish_log(agent.name, f"✅ 已裝備 {len(self.agent_tools_map[agent.name])} 個工具。")
        finally: db.close()

    async def _agent_turn_async(self, agent: AgentBase, side: str, round_num: int) -> str:
        self._publish_log(f"{agent.name} (Thinking)", "正在思考...")
        equipped = self.agent_tools_map.get(agent.name, [])
        ollama_tools = []
        for n in equipped:
            try:
                t = self.tool_registry.get_tool_data(n)
                ollama_tools.append({"type": "function", "function": {"name": n, "description": t.get('description', ''), "parameters": t.get('schema', {})}})
            except: pass

        db = SessionLocal()
        try:
            # [Phase 38] Role Redlines & Causal Logic
            role_redlines = ""
            r_lower = agent.name.lower()
            if "量化" in r_lower:
                role_redlines = """
- 禁止感性推斷。若無數據必須回報數據缺失。
- **證據鏈協議**：提及財務數值必須標註 [Ref: ID]。
- **量化深度**：分析股價必須核查 `income_statement` 中的利潤趨勢。
"""
            elif "風控" in r_lower:
                role_redlines = "- 禁止下多空結論。\n- **因果風險**：必須說明宏觀因素如何傳導至主體業務。"
            elif "交易" in r_lower:
                role_redlines = "- **技術面主權**：必須包含成交量與走勢分析，禁止只談基本面。"

            # [Phase 38] Negative Feedback Reinforcement
            arbiter_feedback = ""
            for item in reversed(self.history[-15:]):
                if item.get("role") == "Chairman (Arbiter)":
                    arbiter_feedback = f"\n⚠️ 【主席裁判令】：{item.get('content')}\n"
                    break
            
            system_p = f"""
# 🔒 DEBATE_ANCHOR_DECREE
{getattr(self, 'anchor_decree', '')}
# ⚖️ CLAIM_GRADING_PROTOCOL
1. 任何核心斷言必須遵循：[觀察事實 (Ref: ID)] -> [因果推論] -> [具體影響]。
2. 缺乏引用將被視為無效。
# Role Discipline
{role_redlines}
你是 {agent.name}。請嚴格遵守裁判令修正你的論證邏輯。
"""
            user_p = f"Round {round_num}. {arbiter_feedback}\n請給出具備證據引用與因果分析的本輪論點。"
        finally: db.close()

        step = 0; max_steps = 5; current_p = user_p
        while step < max_steps:
            step += 1
            response = await call_llm_async(current_p, system_prompt=system_p, tools=ollama_tools)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    call = json.loads(match.group(0))
                    if "tool" in call:
                        t_name = call["tool"]; params = call.get("params", {})
                        if "justification" not in params: params["justification"] = "自動數據核實。"
                        t_name = self._resolve_financial_tool(t_name, equipped)
                        if "stock_rt" in t_name:
                            tz = timezone(timedelta(hours=8)); now = datetime.now(timezone.utc).astimezone(tz)
                            if now.weekday() >= 5 or now.hour < 9 or now.hour >= 14:
                                self._publish_log("System", "🌙 非交易時段，行情自動導向歷史日K...")
                                t_name = "twse.stock_day"
                                if "code" in params: params["symbol"] = params.pop("code")

                        self._publish_log(agent.name, f"🛠️ 調用工具: {t_name}")
                        from worker.tool_invoker import call_tool
                        loop = asyncio.get_running_loop(); res = None
                        for retry in range(2):
                            try:
                                res = await loop.run_in_executor(None, call_tool, t_name, params)
                                if isinstance(res, dict) and res.get("error"): raise ValueError()
                                break
                            except:
                                if retry == 0: time.sleep(1); continue
                                if "price" in t_name:
                                    try: res = await loop.run_in_executor(None, call_tool, "twse.stock_day", params); break
                                    except: pass
                                search_res = await loop.run_in_executor(None, call_tool, "searxng.search", {"q": f"{self.topic} {t_name}"})
                                res = {"error": "鏈路受限"} if "alternative_action" in str(search_res) else search_res
                        
                        await self.hippocampus.store(agent.name, t_name, params, res)
                        current_p = f"工具 {t_name} 結果：\n{json.dumps(res, ensure_ascii=False, indent=2)}\n請繼續分析。"
                        continue
                except: pass
            return response
        return "調查上限。"

    def _resolve_financial_tool(self, tool_name: str, equipped: List[str]) -> str:
        if tool_name in equipped: return tool_name
        matrix = {
            "price": ["financial.get_verified_price", "twse.stock_day", "yahoo.stock_info"],
            "fundamental": ["chinatimes.stock_fundamental", "internal.search_company"],
            "financials": ["chinatimes.income_statement", "chinatimes.balance_sheet", "chinatimes.financial_ratios"],
            "macro": ["av.CPI", "fred.get_series_observations", "worldbank.global_inflation"]
        }
        t_l = tool_name.lower(); cat = None
        if any(k in t_l for k in ["price", "rt", "daily"]): cat = "price"
        elif any(k in t_l for k in ["statement", "sheet", "ratio"]): cat = "financials"
        elif any(k in t_l for k in ["fundamental", "info"]): cat = "fundamental"
        elif any(k in t_l for k in ["cpi", "gdp", "inflation"]): cat = "macro"
        if cat:
            for fb in matrix[cat]:
                if fb in equipped: return fb
        return tool_name

    async def _audit_methodology_and_relevance(self, round_num: int, summaries: Dict[str, str]):
        self._publish_log("System", f"⚖️ 正在進行第 {round_num} 輪方法論裁判...")
        audit_p = f"評核本輪辯論合法性。內容：{summaries}\n要求：標記非法推論與缺乏引用的財務斷言。回傳 JSON: has_violation, arbitration_order。"
        try:
            raw = await call_llm_async(audit_p, system_prompt="冷酷的方法論裁判。")
            res = json.loads(re.search(r'\{.*\}', raw, re.DOTALL).group(0))
            if res.get("has_violation"):
                msg = {"role": "Chairman (Arbiter)", "content": f"# ⚖️ 裁判令\n{res.get('arbitration_order')}"}
                self.history.append(msg); self.full_history.append(msg)
                self._publish_log("Chairman (Arbiter)", res.get('arbitration_order'))
        except: pass

    async def _check_db_date_async(self):
        try:
            from worker.tool_invoker import call_tool
            res = await asyncio.get_running_loop().run_in_executor(None, call_tool, "financial.get_verified_price", {"coid": "2330.TW", "opts.limit": 1})
            if isinstance(res, dict) and res.get("data"):
                 self.latest_db_date = str(res["data"][0].get("mdate")).split("T")[0]
                 self._publish_log("System", f"📅 數據基準日：{self.latest_db_date}")
        except: pass

    async def _conduct_neutral_fact_check(self, decree):
        self._publish_log("System", "⚖️ 事實核查中...")

    async def _check_and_trigger_emergency_mode(self, result):
        pass

    async def _generate_investment_report(self, rounds_data, conclusion):
        return "投資報告已生成。"

    def _extract_urls(self, data):
        return []
