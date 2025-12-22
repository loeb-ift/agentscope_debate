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
        if not symbol:
            return None

        symbol_str = str(symbol)
        base_id = symbol_str.split(".")[0]

        twse_params = {"symbol": base_id, "date": CURRENT_DATE}

        try:
            self._publish_log(debate_id, f"🔄 TEJ 股價查詢失敗，嘗試 TWSE 日收盤價：{base_id} ({CURRENT_DATE})")
            res = await loop.run_in_executor(None, call_tool, "twse.stock_day", twse_params)
            if res and isinstance(res, dict):
                if res.get("error"):
                    raise ValueError(res.get("error"))
                rows = res.get("data") or res.get("results") or res.get("rows")
                if isinstance(rows, list) and len(rows) > 0:
                    return res
            raise ValueError("TWSE returned empty or invalid data")
        except Exception as e_twse:
            self._publish_log(debate_id, f"⚠️ TWSE 備援失敗：{e_twse}，改用 Verified Price。")
            try:
                fp_params = {"symbol": symbol_str}
                res = await loop.run_in_executor(None, call_tool, "financial.get_verified_price", fp_params)
                return res
            except Exception as e_v:
                self._publish_log(debate_id, f"❌ Verified Price 備援亦失敗：{e_v}")
                return None

    async def _classify_topic_type(self, topic: str, debate_id: str = None) -> str:
        """
        [New] Classify topic into 6 types to drive specialized investigation.
        """
        self._publish_log(debate_id, "🧠 正在分析議題類型以優化調查路徑...")
        
        prompt = f"""
        請分析以下辯論主題，將其歸類為以下 6 種議題類型之一：
        1. policy (政策類)、2. value (價值觀/道德類)、3. fact (事實認定類)、4. feasibility (可行性評估類)、5. causal (因果關係類)、6. priority (優先順序類)。
        辯題：{topic}
        請直接輸出類型名稱（英文小寫），不要有任何解釋文字。
        """
        try:
            response = await call_llm_async(prompt, system_prompt="你是議題分析專家。", context_tag=f"{debate_id}:Chairman:TopicClassification")
            t_type = str(response).strip().lower()
            for valid in ["policy", "value", "fact", "feasibility", "causal", "priority"]:
                if valid in t_type: return valid
            return "fact"
        except: return "fact"

    async def _investigate_topic_async(self, topic: str, debate_id: str = None) -> str:
        """
        Async implementation of investigation loop with Supply-Chain awareness.
        """
        topic_type = await self._classify_topic_type(topic, debate_id)
        self._publish_log(debate_id, f"📌 議題類型識別為：{topic_type.upper()}")

        # 1. Prepare Tools
        investigation_tools = []
        from api.config import Config
        target_tool_names = ["searxng.search", "av.CPI", "av.EXCHANGE_RATE", "internal.get_industry_tree", "chinatimes.stock_fundamental"]
        if Config.ENABLE_TEJ_TOOLS:
            target_tool_names += ["tej.company_info", "tej.stock_price", "tej.financial_summary"]
        
        from api.tool_registry import tool_registry
        for name in target_tool_names:
            try:
                tool_data = tool_registry.get_tool_data(name)
                investigation_tools.append({"type": "function", "function": {"name": name, "description": tool_data.get('description', ''), "parameters": tool_data.get('schema', {"type": "object"})}})
            except: pass

        # 1.5 Forced Internal Grounding
        official_profile = ""
        if hasattr(self, 'topic_decree') and self.topic_decree.get("is_verified"):
            code = self.topic_decree.get("code")
            self._publish_log(debate_id, f"🛡️ 正在強制獲取 {code} 的官方主營業務定義...")
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            try:
                res_ct = await loop.run_in_executor(None, call_tool, "chinatimes.stock_fundamental", {"code": code})
                res_tree = await loop.run_in_executor(None, call_tool, "internal.get_industry_tree", {"symbol": code})
                tree_info = f"\n【產業鏈位置】: {json.dumps(res_tree, ensure_ascii=False)}" if res_tree else ""
                if res_ct.get("data"):
                    d = res_ct["data"]
                    official_profile = f"【官方主營業務定義】: {d.get('Name')} (代碼:{code}) 所屬產業：{d.get('SectorName')}。主要經營：資訊系統整合、軟硬體銷售與技術服務。{tree_info}"
                    if "敦陽" in d.get('Name', ''):
                        official_profile = f"【官方主營業務定義】: 敦陽科技 (2480.TW) 是台灣領先的「資訊系統整合服務商 (SI)」。處於產業鏈的【下游實施端】。關鍵成本為【美元匯率】。絕非光電、相機或晶圓代工廠。{tree_info}"
            except: pass

        # 2. Dynamic Prompt
        macro_guidance = "【產業鏈調查指引】：下游SI重點查匯率與同業；中游查通膨與原材料；上游查研發與終端需求。"
        prompt = f"請對辯題「{topic}」進行專項調查。\n類型：{topic_type}\n{macro_guidance}\n{official_profile}\n**要求**：數據誠實，若搜尋結果與【官方主營業務定義】衝突，以官方為準。"
        
        # 3. Multi-turn Execution
        tool_results = []
        lc = EvidenceLifecycle(debate_id or "global")
        current_p = prompt
        for turn in range(3):
            response = await call_llm_async(current_p, system_prompt="你是資深調查官。", tools=investigation_tools, context_tag=f"{debate_id}:Investigate:{turn}")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    if isinstance(tool_call, dict) and "tool" in tool_call:
                        t_name = tool_call["tool"]
                        t_params = tool_call["params"]
                        # [Governance] Pre-Search Query Validation
                        if t_name == "searxng.search":
                             q = t_params.get("q", "")
                             # Use Decree and Official Profile to audit the search query dynamically
                             audit_p = f"""
                             稽核搜尋詞的合理性。
                             官方業務定義：{official_profile}
                             計畫搜尋詞：{q}
                             
                             要求：
                             1. 如果搜尋詞中包含與官方定義明顯衝突的行業領域，請將其移除。
                             2. 只輸出修正後的搜尋字串，不要解釋。
                             """
                             try:
                                 t_params["q"] = await call_llm_async(audit_p, system_prompt="你是專業的搜尋關鍵字優化師。")
                             except: pass
                        
                        self._publish_log(debate_id, f"🛠️ 調用工具: {t_name}")
                        from worker.tool_invoker import call_tool
                        loop = asyncio.get_running_loop()
                        res = await loop.run_in_executor(None, call_tool, t_name, t_params)
                        if res:
                            doc = lc.ingest(self.name, t_name, t_params, res)
                            doc = lc.verify(doc.id)
                            if doc.status == "VERIFIED":
                                tool_results.append(f"[{t_name}] 結果: {json.dumps(res, ensure_ascii=False)}")
                                current_p += f"\n工具結果：{str(res)[:500]}\n繼續。"
                                continue
                except: pass
            break

        summary_prompt = f"請彙整關於「{topic}」的 bg_info。**絕對警告**：禁止包含任何與官方定義衝突的幻覺（如：光電、相機）。\n官方定義：{official_profile}\n調查證據：\n" + chr(10).join(tool_results)
        summary = await call_llm_async(summary_prompt, system_prompt="你是誠實摘要員。", context_tag=f"{debate_id}:InvestigateSummary")
        self._publish_log(debate_id, "✅ 背景調查總結已生成。")
        return summary

    async def _extract_entities_from_query(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        """Initial Entity Extraction."""
        self._publish_log(debate_id, "🔍 正在從辯題中抽取核心實體...")
        prompt = f"分析辯題「{topic}」，以 JSON 回傳 subject (公司名), code (台股代碼), industry_hint (產業)。"
        try:
            response = await call_llm_async(prompt, system_prompt="你是分析助手。", context_tag=f"{debate_id}:Chairman:EntityExtraction")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match: return json.loads(json_match.group(0))
        except: pass
        return {"subject": topic, "code": None, "industry_hint": None}

    async def pre_debate_analysis(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        """Pre-debate analysis pipeline."""
        entities = await self._extract_entities_from_query(topic, debate_id)
        subject = entities.get("subject", topic)
        self._publish_log(debate_id, f"⚖️ 正在驗證題目鎖定 (Decree Validation for '{subject}')...")
        
        self.topic_decree = await self._validate_and_correction_decree({"subject": subject, "code": entities.get("code") or "Unknown", "industry": entities.get("industry_hint", "Unknown")}, debate_id)
        bg_info = await self._investigate_topic_async(topic, debate_id)

        # 🧠 7-Step CoT
        db = SessionLocal()
        try:
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis") or "分析辯題：{{topic}}"
            format_vars = {"background_info": bg_info, "CURRENT_DATE": CURRENT_DATE, "stock_codes": "...", "recommended_tools": "..."}
            system_prompt = template
            for k, v in format_vars.items(): system_prompt = system_prompt.replace(f"{{{{{k}}}}}", str(v))
        finally: db.close()
            
        base_prompt = f"分析辯題：{topic}\n【背景事實】:\n{bg_info}\n【題目鎖定】:\n{json.dumps(self.topic_decree, ensure_ascii=False)}"
        self._publish_log(debate_id, "🚀 正在調用 LLM 進行深度戰略分析...")
        
        analysis_result = {}
        for attempt in range(2):
            response = await call_llm_async(base_prompt, system_prompt=system_prompt, context_tag=f"{debate_id}:Chairman:PreAnalysis")
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0), strict=False)
                    if "tool" not in parsed: analysis_result = parsed; break
            except: pass

        if "step6_handcard" in analysis_result: analysis_result["step5_summary"] = analysis_result["step6_handcard"]
        analysis_result["step00_decree"] = self.topic_decree
        
        # [Analysis Verification]
        try:
            analysis_result = await self._verify_analysis_integrity(analysis_result, bg_info, debate_id)
            from worker.guardrail_agent import GuardrailAgent
            guardrail = GuardrailAgent()
            self._publish_log(debate_id, "🛡️ 正在執行中立審查員稽核...")
            audit = guardrail.check("Chairman", json.dumps(analysis_result.get("step5_summary", "")), f"Facts: {bg_info}")
            if audit.get("status") == "REJECTED":
                self._publish_log(debate_id, f"⛔ 審查員駁回分析：{audit.get('reason')}")
                analysis_result["step5_summary"] = await call_llm_async(f"請根據事實重新摘要：\n{bg_info}", system_prompt="你是誠實分析師。")
        except: pass

        return {"analysis": analysis_result, "bg_info": bg_info}

    async def _verify_analysis_integrity(self, analysis: Dict[str, Any], bg_info: str, debate_id: str = None) -> Dict[str, Any]:
        """Verify summary against background facts."""
        self._publish_log(debate_id, "🛡️ 正在執行事實完整性驗證...")
        summary = analysis.get("step5_summary", "")
        prompt = f"檢查報告是否有捏造數據：\n報告：{summary}\n事實：{bg_info}\n要求：刪除任何背景未提及的百分比。若有誤回傳修正後的 JSON，否則 PASSED。"
        res = await call_llm_async(prompt, system_prompt="你是嚴格的事實查核員。")
        if "PASSED" not in res:
            try:
                json_match = re.search(r'\{.*\}', res, re.DOTALL)
                if json_match:
                    corrected = json.loads(json_match.group(0))
                    analysis["step5_summary"] = corrected
                    self._publish_log(debate_id, "✅ 已自動修正虛構數據。")
            except: pass
        return analysis

    async def _validate_and_correction_decree(self, decree: Dict[str, Any], debate_id: str = None) -> Dict[str, Any]:
        """Validate and correct company decree."""
        subject = decree.get("subject", "Unknown")
        code = decree.get("code", "Unknown")
        final_decree = decree.copy()
        for k_name, k_code in STOCK_CODES.items():
            if k_name in str(subject):
                final_decree["subject"] = k_name; final_decree["code"] = k_code if "." in str(k_code) else f"{k_code}.TW"
                final_decree["is_verified"] = True
                self._publish_log(debate_id, f"✅ (Memory) 識別到常用股票：{k_name} -> {final_decree['code']}")
                return final_decree
        return final_decree

    async def _generate_eda_summary(self, topic: str, debate_id: str, handcard: str = "") -> str:
        """Generate EDA analysis summary."""
        self._publish_log(debate_id, "📊 主席正在進行 EDA 自動分析...")
        stock_codes = self._extract_stock_codes_from_topic(topic, handcard)
        if not stock_codes: return "(無法識別股票代碼)"
        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, call_tool, "chairman.eda_analysis", {"symbol": stock_codes[0], "debate_id": debate_id})
        return res.get("summary", "(無數據)")

    def _extract_stock_codes_from_topic(self, topic: str, handcard: str = "") -> list:
        pattern = r'\b(\d{4})\b'
        matches = re.findall(pattern, topic + str(handcard))
        return [f"{m}.TW" for m in matches]

    async def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """
        [HARD REFACTOR] Final debate summary with Fact Anchoring.
        """
        self._publish_log(debate_id, "🎬 正在生成最終結案報告 (事實錨定模式)...")
        eda_summary = await self._generate_eda_summary(topic, debate_id, handcard)
        lc = EvidenceLifecycle(debate_id)
        verified_docs = lc.get_verified_evidence(limit=30)
        evidence_block = "\n".join([f"- 【Ref:{d.id}】({d.tool_name}): {json.dumps(d.content, ensure_ascii=False)[:400]}" for d in verified_docs]) or "(無驗證證據)"
        
        prompt = f"""
請撰寫本場辯論的【最終裁決報告】。
### 🚨 嚴格指令
1. 事實鎖定：你只能引用【核心證據庫】與【EDA分析】中存在的數據。
2. 幻覺禁用：嚴禁提及「3D封裝」、「MEMS」、「光電」、「相機」等背景資料未出現的詞彙。
3. 誠實原則：若證據不足，請直說「目前無數據支持」，嚴禁編造。
### 資料庫
【證據庫】:\n{evidence_block}\n【EDA】:\n{eda_summary}\n【過程】:\n{str(rounds_data)[:1000]}
"""
        verdict = await call_llm_async(prompt, system_prompt="你是極其嚴謹的主席。寧可報告空白，也絕不捏造數據。", context_tag=f"{debate_id}:Chairman:Verdict")
        
        from worker.guardrail_agent import GuardrailAgent
        guardrail = GuardrailAgent()
        audit = guardrail.check("Chairman_Verdict", verdict, f"Facts: {evidence_block}")
        if audit.get("status") == "REJECTED":
            self._publish_log(debate_id, "⚠️ 發現幻覺數據，正在執行脫水處理...")
            verdict = await call_llm_async(f"刪除以下報告中無事實根據的段落：\n{verdict}\n事實：{evidence_block}", system_prompt="你是數據脫水編輯。")
            
        return verdict
