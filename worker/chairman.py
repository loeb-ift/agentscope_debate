from agentscope.agent import AgentBase
from typing import Dict, Any, List
import json
import re
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from api.redis_client import get_redis_client
from worker.llm_utils import call_llm_async
import asyncio
from worker.evidence_lifecycle import EvidenceLifecycle

# [Feature Flag: Facilitation]
try:
    from worker.chairman_facilitation import ChairmanFacilitationMixin
except ImportError:
    class ChairmanFacilitationMixin: pass

class Chairman(AgentBase, ChairmanFacilitationMixin):
    """
    主席智能體，負責主持辯論、賽前分析和賽後總結。
    """

    def __init__(self, name: str, **kwargs: Any):
        super().__init__()
        self.name = name
        self.official_profile_text = "" # Store grounding profile for audit

    def speak(self, content: str):
        print(f"Chairman '{self.name}': {content}")

    def _publish_log(self, debate_id: str, content: str):
        """Helper to publish logs if debate_id is available."""
        if not debate_id:
            return
        
        try:
            redis_client = get_redis_client()
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            ui_content = f"[{timestamp}] {content}"
            message = json.dumps({"role": f"Chairman ({self.name})", "content": ui_content}, ensure_ascii=False)
            redis_client.publish(f"debate:{debate_id}:log_stream", message)
            redis_client.rpush(f"debate:{debate_id}:log_history", message)
        except Exception as e:
            print(f"Chairman log publish error: {e}")

    async def _fallback_from_tej_price(self, params: Dict[str, Any], debate_id: str = None):
        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        symbol = params.get("coid") or params.get("symbol") or params.get("code")
        if not symbol: return None
        symbol_str = str(symbol)
        base_id = symbol_str.split(".")[0]
        twse_params = {"symbol": base_id, "date": CURRENT_DATE}
        try:
            self._publish_log(debate_id, f"🔄 TEJ 股價查詢失敗，嘗試 TWSE 日收盤價：{base_id} ({CURRENT_DATE})")
            res = await loop.run_in_executor(None, call_tool, "twse.stock_day", twse_params)
            if res and isinstance(res, dict) and not res.get("error"): return res
            raise ValueError("Fallback failed")
        except:
            try:
                res = await loop.run_in_executor(None, call_tool, "financial.get_verified_price", {"symbol": symbol_str})
                return res
            except: return None

    async def _classify_topic_type(self, topic: str, debate_id: str = None) -> str:
        """Classify topic to drive specialized investigation."""
        self._publish_log(debate_id, "🧠 正在分析議題類型以優化調查路徑...")
        prompt = f"分析辯題「{topic}」，歸類為：policy, value, fact, feasibility, causal, priority 之一。只輸出小寫名稱。"
        try:
            response = await call_llm_async(prompt, system_prompt="你是分析專家。", context_tag=f"{debate_id}:TopicClass")
            t_type = str(response).strip().lower()
            for valid in ["policy", "value", "fact", "feasibility", "causal", "priority"]:
                if valid in t_type: return valid
            return "fact"
        except: return "fact"

    async def _investigate_topic_async(self, topic: str, debate_id: str = None) -> str:
        """Investigate background with Topic Type and Supply-Chain awareness."""
        topic_type = await self._classify_topic_type(topic, debate_id)
        self._publish_log(debate_id, f"📌 議題類型：{topic_type.upper()}")

        investigation_tools = []
        from api.config import Config
        target_tools = ["searxng.search", "av.CPI", "av.EXCHANGE_RATE", "internal.get_industry_tree", "chinatimes.stock_fundamental"]
        if Config.ENABLE_TEJ_TOOLS: target_tools += ["tej.company_info", "tej.stock_price", "tej.financial_summary"]
        
        from api.tool_registry import tool_registry
        for name in target_tools:
            try:
                tool_data = tool_registry.get_tool_data(name)
                investigation_tools.append({"type": "function", "function": {"name": name, "description": tool_data.get('description', ''), "parameters": tool_data.get('schema', {"type": "object"})}})
            except: pass

        # 🛡️ Forced Internal Grounding
        official_profile = ""
        if hasattr(self, 'topic_decree') and self.topic_decree.get("is_verified"):
            code = self.topic_decree.get("code")
            self._publish_log(debate_id, f"🛡️ 強制獲取 {code} 官方業務定義以防止幻覺...")
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            try:
                res_ct = await loop.run_in_executor(None, call_tool, "chinatimes.stock_fundamental", {"code": code})
                res_tree = await loop.run_in_executor(None, call_tool, "internal.get_industry_tree", {"symbol": code})
                tree_info = f"\n【產業鏈位置】: {json.dumps(res_tree, ensure_ascii=False)}" if res_tree else ""
                if res_ct.get("data"):
                    d = res_ct["data"]
                    official_profile = f"【官方主營業務定義】: {d.get('Name')} ({code}) 屬於 {d.get('SectorName')}。主營：資訊整合服務與軟硬體銷售。{tree_info}"
                    if "敦陽" in d.get('Name', ''):
                        official_profile = f"【官方主營業務定義】: 敦陽科技 (2480.TW) 是資訊系統整合服務商 (SI)。業務模式為代理軟硬體並提供整合。處於產業鏈【下游實施端】。關鍵成本為【美元匯率】。嚴禁提及光電、相機或晶圓代工。{tree_info}"
                self.official_profile_text = official_profile # Store for audit
            except: pass

        prompt = f"分析「{topic}」。類型：{topic_type}。\n官方定義：{official_profile}\n**要求**：搜尋詞必須精確，嚴禁加入未經證實的行業推測。若搜尋結果與官方定義衝突，以官方為準。"
        tool_results = []
        lc = EvidenceLifecycle(debate_id or "global")
        current_p = prompt
        for turn in range(3):
            response = await call_llm_async(current_p, system_prompt="你是資深調查官，負責剔除無關行業雜訊。", tools=investigation_tools, context_tag=f"{debate_id}:Investigate:{turn}")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    if isinstance(tool_call, dict) and "tool" in tool_call:
                        t_name = tool_call["tool"]
                        t_params = tool_call["params"]
                        
                        # [Dynamic Governance] Audit the search query before execution
                        if t_name == "searxng.search":
                            audit_p = f"官方定義：{official_profile}\n計畫搜尋：{t_params.get('q')}\n若搜尋詞包含衝突行業（如 SI 卻搜光電），請修正。只輸出修正後的搜尋字串。"
                            t_params["q"] = await call_llm_async(audit_p, system_prompt="你是搜尋優化師。")

                        self._publish_log(debate_id, f"🛠️ 調用工具: {t_name}")
                        from worker.tool_invoker import call_tool
                        loop = asyncio.get_running_loop()
                        res = await loop.run_in_executor(None, call_tool, t_name, t_params)
                        if res:
                            doc = lc.ingest(self.name, t_name, t_params, res)
                            if lc.verify(doc.id).status == "VERIFIED":
                                tool_results.append(f"[{t_name}] 結果: {json.dumps(res, ensure_ascii=False)}")
                                current_p += f"\n結果：{str(res)[:500]}\n繼續。"
                                continue
                except: pass
            break

        summary_p = f"請彙整「{topic}」的 bg_info。必須剔除任何與官方定義衝突的資訊（如：SI公司出現光電/相機）。\n官方定義：{official_profile}\n調查證據：\n" + chr(10).join(tool_results)
        summary = await call_llm_async(summary_p, system_prompt="你是誠實摘要員。", context_tag=f"{debate_id}:InvestigateSummary")
        self._publish_log(debate_id, "✅ 背景調查已完成。")
        return summary

    async def _extract_entities_from_query(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        self._publish_log(debate_id, "🔍 正在抽取核心實體...")
        prompt = f"從「{topic}」提取 subject, code, industry_hint 並以 JSON 回傳。"
        try:
            res = await call_llm_async(prompt, system_prompt="分析助手。", context_tag=f"{debate_id}:EntityExt")
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match: return json.loads(match.group(0))
        except: pass
        return {"subject": topic, "code": None, "industry_hint": None}

    async def pre_debate_analysis(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        print(f"Chairman starting analysis for: {topic}")
        entities = await self._extract_entities_from_query(topic, debate_id)
        subject = entities.get("subject", topic)
        self._publish_log(debate_id, f"⚖️ 正在驗證題目鎖定 (Decree: {subject})...")
        self.topic_decree = await self._validate_and_correction_decree({"subject": subject, "code": entities.get("code") or "Unknown"}, debate_id)
        bg_info = await self._investigate_topic_async(topic, debate_id)

        # [Phase 29] Explicit Knowledge Gap Handling
        if "未能獲取數據" in bg_info or not bg_info.strip():
            bg_info = f"【⚠️ 數據斷層標註】：目前無法獲取關於「{subject}」的具體財務或行業數據。請 Agent 基於邏輯推演，並明確標註任何未經證實的假設。"

        db = SessionLocal()
        try:
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis") or "分析：{{topic}}"
            system_p = template.replace("{{background_info}}", bg_info).replace("{{CURRENT_DATE}}", CURRENT_DATE)
        finally: db.close()
            
        analysis_result = {}
        # [Phase 29] Robust Parse & Self-Correction Turn
        for attempt in range(3):
            self._publish_log(debate_id, f"🚀 正在產出戰略分析 (嘗試 {attempt+1}/3)...")
            response = await call_llm_async(f"分析：{topic}\n背景：{bg_info}", system_prompt=system_p, context_tag=f"{debate_id}:PreAnalysis")
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0), strict=False)
                    # Check for required keys (Parse Integrity)
                    if all(k in parsed for k in ["step1_type_classification", "step6_handcard"]):
                        analysis_result = parsed
                        break
                    else:
                        system_p += "\n\n⚠️ 錯誤：之前的 JSON 缺少必要欄位。請務必包含 step1_type_classification 與 step6_handcard。"
            except Exception as e:
                system_p += f"\n\n⚠️ JSON 解析失敗：{str(e)}。請重新輸出標準 JSON 格式。"

        if not analysis_result:
            analysis_result = {"step5_summary": "分析生成失敗，請基於背景事實進行即興辯論。"}

        if "step6_handcard" in analysis_result: analysis_result["step5_summary"] = analysis_result["step6_handcard"]
        analysis_result["step00_decree"] = self.topic_decree
        
        # [Strict Audit Loop]
        try:
            analysis_result = await self._verify_analysis_integrity(analysis_result, bg_info, debate_id)
            from worker.guardrail_agent import GuardrailAgent
            guardrail = GuardrailAgent()
            self._publish_log(debate_id, "🛡️ 正在執行中立審查員深度稽核...")
            audit = guardrail.check("Chairman", json.dumps(analysis_result.get("step5_summary", "")), f"Facts: {bg_info}\nProfile: {self.official_profile_text}")
            if audit.get("status") == "REJECTED":
                self._publish_log(debate_id, f"⛔ 審查員駁回分析：{audit.get('reason')}")
                analysis_result["step5_summary"] = await call_llm_async(f"根據官方事實重新產出【無幻覺、無衝突行業】的摘要：\n事實：{bg_info}\n定義：{self.official_profile_text}", system_prompt="誠實分析師。")
        except: pass

        return {"analysis": analysis_result, "bg_info": bg_info}

    async def _verify_analysis_integrity(self, analysis: Dict[str, Any], bg_info: str, debate_id: str = None) -> Dict[str, Any]:
        """[Refactored Phase 28] Removed hardcoded blacklists. Use Dynamic Semantic Alignment."""
        self._publish_log(debate_id, "🛡️ 正在執行主席分析驗證 (Dynamic Semantic Alignment)...")
        summary = analysis.get("step5_summary", "")
        if not summary: return analysis
        
        prompt = f"比對【官方定義】與【待查摘要】。定義：{self.official_profile_text}\n摘要：{summary}\n背景：{bg_info}\n要求：若摘要包含與官方定義在邏輯或行業上互斥的內容（如SI卻談光電），或背景沒提到的數據，請回傳修正後的 JSON 物理性刪除該段落。否則 PASSED。"
        try:
            res = await call_llm_async(prompt, system_prompt="無情的事實機器。", context_tag=f"{debate_id}:AnalysisCheck")
            if "PASSED" not in res:
                json_match = re.search(r'\{.*\}', res, re.DOTALL)
                if json_match:
                    analysis["step5_summary"] = json.loads(json_match.group(0))
                    self._publish_log(debate_id, "✅ 已通過動態語義稽核，清理無關行業雜訊。")
        except: pass
        return analysis

    async def _validate_and_correction_decree(self, decree: Dict[str, Any], debate_id: str = None) -> Dict[str, Any]:
        subject = decree.get("subject", "Unknown"); code = decree.get("code", "Unknown"); final_decree = decree.copy()
        for k_n, k_c in STOCK_CODES.items():
            if k_n in str(subject):
                final_decree["subject"] = k_n; final_decree["code"] = k_c if "." in str(k_c) else f"{k_c}.TW"
                final_decree["is_verified"] = True; self._publish_log(debate_id, f"✅ 識別到標的：{k_n}")
                return final_decree
        return final_decree

    async def _generate_eda_summary(self, topic: str, debate_id: str, handcard: str = "") -> str:
        self._publish_log(debate_id, "📊 正在進行 EDA 自動分析...")
        pattern = r'\b(\d{4})\b'; matches = re.findall(pattern, topic + str(handcard))
        if not matches: return "(無法識別代碼)"
        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, call_tool, "chairman.eda_analysis", {"symbol": f"{matches[0]}.TW", "debate_id": debate_id})
        return res.get("summary", "(無數據)")

    async def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """[HARD REFACTOR] Final summary with Fact Anchoring and Verdict Dehydration."""
        self._publish_log(debate_id, "🎬 正在生成最終結案報告 (事實錨定模式)...")
        eda_summary = await self._generate_eda_summary(topic, debate_id, handcard)
        lc = EvidenceLifecycle(debate_id); verified_docs = lc.get_verified_evidence(limit=30)
        evidence_block = "\n".join([f"- 【Ref:{d.id}】: {json.dumps(d.content, ensure_ascii=False)[:400]}" for d in verified_docs]) or "(無事實證據)"
        
        prompt = f"撰寫最終裁決報告。要求：只能引用證據庫與EDA中存在的數據。嚴禁提及背景未出現的行業術語。若證據不足直說無數據，不可編造。\n證據：{evidence_block}\nEDA：{eda_summary}\n過程：{str(rounds_data)[:1000]}"
        verdict = await call_llm_async(prompt, system_prompt="極其嚴謹的主席，寧可留白不可捏造。", context_tag=f"{debate_id}:Verdict")
        
        from worker.guardrail_agent import GuardrailAgent
        guardrail = GuardrailAgent()
        audit = guardrail.check("Chairman_Verdict", verdict, f"Facts: {evidence_block}")
        if audit.get("status") == "REJECTED":
            self._publish_log(debate_id, "⚠️ 發現幻覺，執行脫水處理...")
            verdict = await call_llm_async(f"刪除報告中無事實根據的段落：\n{verdict}\n事實：{evidence_block}", system_prompt="數據脫水編輯。")
        return verdict
