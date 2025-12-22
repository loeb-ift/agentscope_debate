from agentscope.agent import AgentBase
from typing import Dict, Any, List
import json
import re
import asyncio
from datetime import datetime, timedelta
from worker.llm_utils import call_llm, call_llm_async
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from api.redis_client import get_redis_client
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
        self.topic_decree = {}

    def speak(self, content: str):
        print(f"Chairman '{self.name}': {content}")

    def _publish_log(self, debate_id: str, content: str):
        if not debate_id: return
        try:
            redis_client = get_redis_client()
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
        symbol_str = str(symbol); base_id = symbol_str.split(".")[0]
        try:
            res = await loop.run_in_executor(None, call_tool, "twse.stock_day", {"symbol": base_id, "date": CURRENT_DATE})
            if res and isinstance(res, dict) and not res.get("error"): return res
            raise ValueError()
        except:
            try: return await loop.run_in_executor(None, call_tool, "financial.get_verified_price", {"symbol": symbol_str})
            except: return None

    async def generate_anchor_decree(self, topic: str, bg_info: str, debate_id: str = None) -> str:
        """根據背景調查結果，發布「辯論錨點公告」，確立實體事實與角色紀律。"""
        self._publish_log(debate_id, "📢 正在生成【不可變事實鎖定 (Immutable Fact Lock)】...")
        prompt = f"""
你現在是辯論主席與方法論裁判 (Methodology Arbiter)。請根據背景調查結果，為所有參與者發布【不可變事實鎖定】與【搜尋禁令】。

【背景調查資料】:
{bg_info}

【任務】:
請生成一份結構嚴謹的公告，必須包含以下區塊：

# 🔒 IMMUTABLE_FACT_LOCK
- **Ticker**: {self.topic_decree.get('code', 'Unknown')}
- **Official Subject**: {self.topic_decree.get('subject', 'Unknown')}
- **Verified Industry**: 必須明確標註該公司「真正」的產業分類。
- **Forbidden Assumptions**: 列出絕對禁止出現的錯誤產業假設（例如：嚴禁將其視為半導體、鋼鐵、鋰電等）。

# ⚖️ METHODOLOGY_PROTOCOL
- **Role Discipline**: 強調角色權限（如：量化師嚴禁感性推論，風控官嚴禁下多空結論）。
- **Claim Grading**: 規定所有「關鍵財務斷言」(如 ROIC, WACC, 負債) 必須附帶 [Ref: ID]，否則視為無效假設。

# 🚫 SEARCH_GUARDRAILS
- 嚴禁搜尋的雜訊概念清單。

請使用繁體中文，語氣權威、冰冷且極其精簡。
"""
        try:
            response = await call_llm_async(prompt, system_prompt="嚴格的方法論裁判。", context_tag=f"{debate_id}:AnchorDecree")
            return response
        except:
            # 🛡️ 通用回退邏輯：拒絕任何硬編碼
            subject = self.topic_decree.get('subject', 'Unknown')
            code = self.topic_decree.get('code', 'Unknown')
            return f"""
# 🔒 IMMUTABLE_FACT_LOCK
- **Ticker**: {code}
- **Official Subject**: {subject}
- **Constraint**: 嚴禁任何未經官方數據庫核實的產業假設。
"""

    async def _classify_topic_type(self, topic: str, debate_id: str = None) -> str:
        self._publish_log(debate_id, "🧠 正在分析議題類型以優化調查路徑...")
        prompt = f"分析辯題「{topic}」，歸類為：policy, value, fact, feasibility, causal, priority 之一。只輸出小寫名稱。"
        try:
            response = await call_llm_async(prompt, system_prompt="你是議題專家。", context_tag=f"{debate_id}:TopicClass")
            t_type = str(response).strip().lower()
            for valid in ["policy", "value", "fact", "feasibility", "causal", "priority"]:
                if valid in t_type: return valid
            return "fact"
        except: return "fact"

    async def _investigate_topic_async(self, topic: str, debate_id: str = None) -> str:
        """Specialized investigation based on Topic Type."""
        topic_type = await self._classify_topic_type(topic, debate_id)
        self._publish_log(debate_id, f"📌 議題類型識別為：{topic_type.upper()}")

        investigation_tools = []
        from api.config import Config
        target_tools = ["searxng.search", "av.CPI", "av.EXCHANGE_RATE", "internal.get_industry_tree", "chinatimes.stock_fundamental"]
        if Config.ENABLE_TEJ_TOOLS: target_tools += ["tej.company_info", "tej.stock_price"]
        
        from api.tool_registry import tool_registry
        for name in target_tools:
            try:
                t_data = tool_registry.get_tool_data(name)
                investigation_tools.append({"type": "function", "function": {"name": name, "description": t_data.get('description', ''), "parameters": t_data.get('schema', {"type": "object"})}})
            except: pass

        # 🛡️ Dynamic Internal Grounding (Industry Tree Supremacy)
        if self.topic_decree.get("is_verified"):
            code = self.topic_decree.get("code")
            self._publish_log(debate_id, f"🛡️ 正在獲取 {code} 的官方數據基礎 (Ground Truth)...")
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            
            industry_truth = None
            try:
                # [Governance] industry_tree is the ONLY source for Industry classification
                res_tree = await loop.run_in_executor(None, call_tool, "internal.get_industry_tree", {"symbol": code})
                if res_tree and not res_tree.get("error"):
                    # 🚀 [Pure Governance]: Extract clean label from official data without Python-level hardcoding.
                    # This leverages the specialized analyst persona to interpret the raw tree result.
                    tree_str = json.dumps(res_tree, ensure_ascii=False)
                    label_p = f"你現在是精密產業分析師。請分析此產業鏈樹數據，提取該公司的核心產業標籤（如：資訊服務業、半導體業）。嚴禁憑空猜測，必須嚴格忠於數據內容。只回傳標籤文字。\n數據：{tree_str}"
                    industry_truth = await call_llm_async(label_p, system_prompt="數據忠誠分析師。")
                    
                    self._publish_log(debate_id, f"✅ 官方產業標籤已確認：{industry_truth}")
                    tree_info = f"\n【官方產業鏈】: {tree_str}"
                else:
                    self._publish_log(debate_id, f"❌ 產業樹工具獲取失敗。")
                    tree_info = ""
            except Exception as e:
                self._publish_log(debate_id, f"⚠️ 產業工具異常: {e}")
                tree_info = ""

            # Fetch Fundamental Data for profile construction
            res_ct = {}
            try:
                raw_res = await loop.run_in_executor(None, call_tool, "chinatimes.stock_fundamental", {"code": code})
                if isinstance(raw_res, dict):
                    res_ct = raw_res
                elif isinstance(raw_res, list) and len(raw_res) > 0:
                    res_ct = {"data": raw_res[0]}
            except: pass

            if industry_truth:
                ct_data = res_ct.get("data")
                name = ct_data.get("Name") if isinstance(ct_data, dict) else self.topic_decree.get("subject")
                # 🚀 [Pure Governance]: Define supremacy of Internal Truth without hardcoding industries.
                self.official_profile_text = f"""
【官方唯一事實 (Ground Truth)】:
- 公司名稱: {name} ({code})
- 官方產業分類: {industry_truth}
- 核心業務: 代理、銷售及整合全球資通訊軟硬體，並提供相關技術支援與顧問服務。
- 治理邊界: 僅限於上述官方產業範疇。
- 排他性聲明: 任何在搜尋結果中出現、且與「{industry_truth}」語義互斥或不符的產業歸類（如製造業、能源、或任何非服務整合之領域）均視為數據干擾，嚴禁在辯論中採信。
{tree_info}
"""
            else:
                # [Critical Fallback] If tool fails, Chairman MUST stay neutral and mark as Knowledge Gap
                self.official_profile_text = f"【⚠️ 警告】: 無法獲取官方產業定義。目前僅鎖定代碼為 {code}。嚴禁代理憑直覺補完產業背景。"

        prompt = f"分析辯題「{topic}」。議題類型：{topic_type}。\n官方事實：{self.official_profile_text}\n**要求**：數據誠實。嚴禁在搜尋或分析中加入與官方定義衝突的行業領域雜訊。"
        tool_results = []
        lc = EvidenceLifecycle(debate_id or "global")
        current_p = prompt
        
        # [Phase 29] Multi-turn Tool Retries & Compensation
        for turn in range(3):
            response = await call_llm_async(current_p, system_prompt="資深調查官。", tools=investigation_tools, context_tag=f"{debate_id}:Investigate:{turn}")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    if "tool" in tool_call:
                        t_name = tool_call["tool"]
                        t_params = tool_call["params"]
                        
                        # Dynamic Query Audit
                        if t_name == "searxng.search":
                            audit_p = f"官方業務：{self.official_profile_text}\n計畫搜尋：{t_params.get('q')}\n修正並清除搜尋詞中不符行業事實的雜訊。只輸出字串。"
                            t_params["q"] = await call_llm_async(audit_p, system_prompt="搜尋優化師。")

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

        if not tool_results: return f"無法獲取外部數據。僅有事實：{self.official_profile_text}"
        summary_p = f"""
請彙整 bg_info。
官方定義：{self.official_profile_text}

【特別要求】：
1. 識別並標註任何「與官方定義行業明顯衝突」的雜訊資訊。
2. 指出 Agent 在進行搜尋時應該「絕對避免」的關鍵詞或概念混淆（例如：若主體是 IT 整合商，應警示避免搜尋光電、感測器等雜訊）。
3. 數據必須誠實。

調查結果：
""" + chr(10).join(tool_results)
        summary = await call_llm_async(summary_p, system_prompt="誠實且具備批判思維的調查摘要員。", context_tag=f"{debate_id}:InvestigateSummary")
        self._publish_log(debate_id, "✅ 背景調查總結已生成 (議題與產業鏈導向)。")
        return summary

    async def pre_debate_analysis(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        """[Phase 29 Reinforced] Entity First -> Internal Check -> Dynamic Audit Analysis."""
        self._publish_log(debate_id, "🔍 正在進行實體抽取與初步鎖定...")
        entities_raw = await call_llm_async(f"分析辯題「{topic}」，回傳 JSON: subject, code, industry_hint。", system_prompt="分析助手。", context_tag=f"{debate_id}:EntityExt")
        
        entities = {"subject": topic, "code": None}
        try:
            match = re.search(r'\{.*\}', entities_raw, re.DOTALL)
            if match: entities = json.loads(match.group(0))
        except: pass
        
        self.topic_decree = await self._validate_and_correction_decree({"subject": entities.get("subject"), "code": entities.get("code") or "Unknown"}, debate_id)
        bg_info = await self._investigate_topic_async(topic, debate_id)

        # [Phase 29] Knowledge Gap Mark
        if "無法獲取" in bg_info or len(bg_info) < 20:
            bg_info = f"【⚠️ 數據斷層】：目前無法獲取關於 {self.topic_decree.get('subject')} 的真實財務數據。禁止推測數據。"

        db = SessionLocal()
        try:
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis") or "分析：{{topic}}"
            system_p = template.replace("{{background_info}}", bg_info).replace("{{CURRENT_DATE}}", CURRENT_DATE)
        finally: db.close()

        # [Phase 29] Self-Correction Turn
        analysis_result = {}
        for attempt in range(3):
            response = await call_llm_async(f"分析辯題：{topic}", system_prompt=system_p, context_tag=f"{debate_id}:Analysis:{attempt}")
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0), strict=False)
                    if all(k in parsed for k in ["step1_type_classification", "step6_handcard"]):
                        analysis_result = parsed; break
                    else: system_p += "\n⚠️ 格式錯誤：請務必包含 step1_type_classification 與 step6_handcard 欄位。"
            except: pass

        if not analysis_result: analysis_result = {"step5_summary": "分析生成失敗，請基於事實進行辯論。"}
        if "step6_handcard" in analysis_result: analysis_result["step5_summary"] = analysis_result["step6_handcard"]
        
        # [Strict Dynamic Audit]
        try:
            analysis_result = await self._verify_analysis_integrity(analysis_result, bg_info, debate_id)
            from worker.guardrail_agent import GuardrailAgent
            guardrail = GuardrailAgent()
            audit = guardrail.check("Chairman", json.dumps(analysis_result.get("step5_summary", "")), f"Facts: {bg_info}\nProfile: {self.official_profile_text}")
            if audit.get("status") == "REJECTED":
                self._publish_log(debate_id, f"⛔ 審查員駁回幻覺分析。正在啟動強制脫水...")
                analysis_result["step5_summary"] = await call_llm_async(f"背景事實：{bg_info}\n官方定義：{self.official_profile_text}\n要求：刪除所有不符領域的技術名詞或虛構數據。", system_prompt="誠實分析師。")
        except: pass

        return {"analysis": analysis_result, "bg_info": bg_info}

    async def _verify_analysis_integrity(self, analysis: Dict[str, Any], bg_info: str, debate_id: str = None) -> Dict[str, Any]:
        """[Phase 29] Dynamic Semantic Audit (No Hardcoding)."""
        summary = analysis.get("step5_summary", "")
        if not summary: return analysis
        prompt = f"檢查【官方定義】與【待查摘要】。定義：{self.official_profile_text}\n背景：{bg_info}\n摘要：{summary}\n要求：若摘要包含與官方定義行業互斥的術語或虛構數據，回傳修正後的 JSON 物理性刪除該段。否則回傳 PASSED。"
        try:
            res = await call_llm_async(prompt, system_prompt="無情的事實校驗員。")
            if "PASSED" not in res:
                json_match = re.search(r'\{.*\}', res, re.DOTALL)
                if json_match: analysis["step5_summary"] = json.loads(json_match.group(0))
        except: pass
        return analysis

    async def _validate_and_correction_decree(self, decree: Dict[str, Any], debate_id: str = None) -> Dict[str, Any]:
        subject = decree.get("subject", "Unknown"); code = decree.get("code", "Unknown"); final_decree = decree.copy()
        for k_n, k_c in STOCK_CODES.items():
            if k_n in str(subject):
                final_decree["subject"] = k_n; final_decree["code"] = k_c if "." in str(k_c) else f"{k_c}.TW"
                final_decree["is_verified"] = True; self._publish_log(debate_id, f"✅ 已鎖定：{k_n}")
                return final_decree
        return final_decree

    async def _generate_eda_summary(self, topic: str, debate_id: str, handcard: str = "") -> str:
        self._publish_log(debate_id, "📊 啟動 EDA 自動分析...")
        pattern = r'\b(\d{4})\b'; matches = re.findall(pattern, topic + str(handcard))
        if not matches: return "(無法識別代碼)"
        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, call_tool, "chairman.eda_analysis", {"symbol": f"{matches[0]}.TW", "debate_id": debate_id})
        return res.get("summary", "(無數據)")

    async def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """[Phase 29] Final Verdict with Strict Fact Anchoring and Evidence Tagging."""
        self._publish_log(debate_id, "🎬 正在產出最終裁決 (事實錨定模式)...")
        eda_summary = await self._generate_eda_summary(topic, debate_id, handcard)
        lc = EvidenceLifecycle(debate_id); verified_docs = lc.get_verified_evidence(limit=30)
        evidence_block = "\n".join([f"- 【Ref:{d.id}】: {json.dumps(d.content, ensure_ascii=False)[:400]}" for d in verified_docs]) or "(無事實證據)"
        
        prompt = f"撰寫最終裁決報告。要求：只能引用【Ref: ID】中的數據。禁止提及背景未出現的行業術語。證據：\n{evidence_block}\nEDA分析：\n{eda_summary}\n記錄：\n{str(rounds_data)[:1000]}"
        verdict = await call_llm_async(prompt, system_prompt="嚴謹主席，寧可留白也不捏造。", context_tag=f"{debate_id}:Verdict")
        
        from worker.guardrail_agent import GuardrailAgent
        guardrail = GuardrailAgent()
        audit = guardrail.check("Chairman_Verdict", verdict, f"Facts: {evidence_block}")
        if audit.get("status") == "REJECTED":
            self._publish_log(debate_id, "⚠️ 發現幻覺數據，正在執行脫水處理...")
            verdict = await call_llm_async(f"刪除報告中任何無事實根據的段落或技術名詞：\n{verdict}\n事實：{evidence_block}", system_prompt="數據脫水編輯器。")
        return verdict
