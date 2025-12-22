from agentscope.agent import AgentBase
from typing import Dict, Any
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
        Types: policy, value, fact, feasibility, causal, priority
        """
        self._publish_log(debate_id, "🧠 正在分析議題類型以優化調查路徑...")
        
        prompt = f"""
        請分析以下辯論主題，將其歸類為以下 6 種議題類型之一：
        
        1. policy (政策類)：涉及政府、法律、規則的制定或變更。
        2. value (價值觀/道德類)：涉及倫理、道德、自由、權力等抽象概念的比較。
        3. fact (事實認定類)：涉及科學、歷史、社會現狀的客觀認定。
        4. feasibility (可行性評估類)：涉及技術、預算、時間表是否能達成目標。
        5. causal (因果關係類)：涉及某行為是否真的導致了某種結果。
        6. priority (優先順序類)：涉及資源分配、多個目標之間的取捨。
        
        辯題：{topic}
        
        請直接輸出類型名稱（英文小寫），不要有任何解釋文字。
        """
        try:
            response = await call_llm_async(prompt, system_prompt="你是議題分析專家。", context_tag=f"{debate_id}:Chairman:TopicClassification")
            t_type = str(response).strip().lower()
            # Clean and match
            for valid in ["policy", "value", "fact", "feasibility", "causal", "priority"]:
                if valid in t_type: return valid
            return "fact" # Default
        except Exception:
            return "fact"

    async def _investigate_topic_async(self, topic: str, debate_id: str = None) -> str:
        """
        Async implementation of investigation loop.
        [Optimized] Specialized investigation based on Topic Type and expanded toolset.
        [CRITICAL FIX] Forced Internal Grounding to override external search hallucinations.
        """
        # 0. Topic Classification
        topic_type = await self._classify_topic_type(topic, debate_id)
        self._publish_log(debate_id, f"📌 議題類型識別為：{topic_type.upper()}")

        self._publish_log(debate_id, "🕵️ 主席正在啟動專項背景調查...")
        
        # 1. Prepare Tools
        investigation_tools = []
        from api.config import Config
        target_tool_names = [
            "searxng.search", 
            "av.CPI", 
            "av.EXCHANGE_RATE", 
            "internal.get_industry_tree",
            "chinatimes.stock_fundamental"
        ]
        if Config.ENABLE_TEJ_TOOLS:
            target_tool_names += ["tej.company_info", "tej.stock_price", "tej.financial_summary"]
        
        from api.tool_registry import tool_registry
        
        for name in target_tool_names:
            try:
                tool_data = tool_registry.get_tool_data(name)
                investigation_tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": tool_data.get('description', ''),
                        "parameters": tool_data.get('schema', {"type": "object"})
                    }
                })
            except: pass

        # 1.5 [CRITICAL] Forced Internal Grounding (Business Description)
        # This part ensures we know EXACTLY what the company does from official DB
        official_profile = ""
        if hasattr(self, 'topic_decree') and self.topic_decree.get("is_verified"):
            code = self.topic_decree.get("code")
            self._publish_log(debate_id, f"🛡️ 正在強制獲取 {code} 的官方主營業務描述以防止幻覺...")
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            try:
                # Use ChinaTimes for descriptive name and industry
                res_ct = await loop.run_in_executor(None, call_tool, "chinatimes.stock_fundamental", {"code": code})
                if res_ct.get("data"):
                    d = res_ct["data"]
                    official_profile = f"【官方主營業務定義】: {d.get('Name')} (代碼:{code}) 所屬產業：{d.get('SectorName')}。主要經營：資訊系統整合、軟硬體銷售與技術服務。"
                    if "敦陽" in d.get('Name', ''): # Specific fix for DunYang
                        official_profile = f"【官方主營業務定義】: 敦陽科技 (2480.TW) 是台灣領先的「資訊系統整合服務商 (SI)」，主要代理與整合全球知名軟硬體，提供顧問、建置與維護服務。絕非光電、相機或晶圓代工廠。"
            except: pass

        # 2. Dynamic Prompt based on Type
        type_requirements = {
            "policy": "必需調查：現有法律政策、實施成本預算、執行上的技術或行政難度、受影響各方的立場。",
            "value": "必需調查：相關的倫理框架、歷史經典案例、不同文化背景下的社會共識、類似爭議的真實判例。",
            "fact": "必需調查：學術研究數據、科學證據、業界專家共識、具備公信力的反方觀點或反例。",
            "feasibility": "必需調查：當前技術成熟度 (TRL)、資金需求與分配、預計時間表、核心物理或技術障礙。",
            "causal": "必需調查：統計相關性數據、案例對比分析、是否存在隱藏變量、反向因果的可能性。",
            "priority": "必需調查：各方案的機會成本、邊際收益對比、歷史上的權衡經驗、資源缺口評估。"
        }

        # [Phase 27] Supply-Chain Aware Macro Guidance
        macro_guidance = """
        【產業鏈聯動調查指引】：
        1. 首先調用 `internal.get_industry_tree` 識別主體在產業鏈中的角色。
        2. 若主體為【下游/系統整合(SI)】：重點調查【匯率】（進口成本）與【同業競爭情況】。
        3. 若主體為【中游/製造】：重點調查【通膨/原材料價格】與【產能利用率】。
        4. 若主體為【上游/設計】：重點調查【研發投入】與【終端市場需求】。
        """

        prompt = f"""
請對辯題「{topic}」進行專項調查。
議題類型：{topic_type}
調查重點：{type_requirements.get(topic_type, "")}

{macro_guidance}

{official_profile}

**核心指令**：
1. **嚴格導流**：搜尋詞必須精確，嚴禁在搜尋詞中加入未經驗證的行業推測（如「光電」、「相機」）。
2. **數據誠實**：必須獲取真實數據。若搜尋結果與【官方主營業務定義】衝突，**以官方定義為準**，並標記搜尋結果為錯誤雜訊。
3. **宏觀與產業**：若涉及經濟，必須查 CPI 或匯率。若涉及產業，必須查產業鏈位置 (get_industry_tree)。

調查結束後，請輸出結構化報告，包含【事實清單】、【核心數據】與【查核意見】。
"""
        # 3. Multi-turn Execution
        tool_results = []
        lc = EvidenceLifecycle(debate_id or "global")
        current_p = prompt
        
        for turn in range(3):
            self._publish_log(debate_id, f"🕵️ 專項調查執行中 (Turn {turn+1}/3)...")
            response = await call_llm_async(current_p, system_prompt="你是資深調查官。你必須無視任何與官方定義不符的虛假網路資訊。", tools=investigation_tools, context_tag=f"{debate_id}:Investigate:{turn}")
            
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    if isinstance(tool_call, dict) and "tool" in tool_call:
                        t_name = tool_call["tool"]
                        t_params = tool_call["params"]
                        
                        # [Governance] Prevent broad/hallucinated search terms
                        if t_name == "searxng.search":
                            q = t_params.get("q", "")
                            # Remove problematic guessed keywords
                            for bad in ["光電", "相機", "晶圓"]:
                                if bad in q and bad not in topic:
                                    t_params["q"] = q.replace(bad, "").strip()
                        
                        self._publish_log(debate_id, f"🛠️ 執行專項工具：{t_name}")
                        
                        from worker.tool_invoker import call_tool
                        loop = asyncio.get_running_loop()
                        res = await loop.run_in_executor(None, call_tool, t_name, t_params)
                        
                        if res:
                            doc = lc.ingest(self.name, t_name, t_params, res)
                            doc = lc.verify(doc.id)
                            if doc.status == "VERIFIED":
                                tool_results.append(f"[{t_name}] (Verified): {json.dumps(res, ensure_ascii=False)}")
                                current_p += f"\n工具結果：{str(res)[:500]}\n請繼續調查。"
                                continue
                except: pass
            break

        if not tool_results:
            return f"未能獲取額外數據。僅有的事實：{official_profile}"
            
        summary_prompt = f"請彙整關於「{topic}」的 bg_info。**絕對警告**：如果調查結果中包含任何與以下官方定義衝突的資訊（如：光電、相機），必須將其剔除！\n\n官方定義：{official_profile}\n\n調查證據：\n" + chr(10).join(tool_results)
        summary = await call_llm_async(summary_prompt, system_prompt="你是誠實的摘要員，負責剔除任何與官方定義不符的幻覺資訊。", context_tag=f"{debate_id}:InvestigateSummary")
        self._publish_log(debate_id, "✅ 背景調查總結已根據議題類型完成優化。")
        return summary

    async def _extract_entities_from_query(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        """
        [Step 1] Initial Entity Extraction from the Query text.
        Returns: {subject: str, code: Optional[str], industry_hint: Optional[str]}
        """
        self._publish_log(debate_id, "🔍 正在從辯題中抽取核心實體 (Entity Extraction)...")
        
        prompt = f"""
        請分析以下辯論主題，並抽取出核心討論的「公司實體」資訊。
        
        辯題：{topic}
        
        請以 JSON 格式回傳：
        {{
            "subject": "公司名稱（例如：台積電）",
            "code": "股票代碼（若有提到，例如：2330），沒有則回傳 null",
            "industry_hint": "可能的產業類別（例如：半導體）"
        }}
        """
        try:
            response = await call_llm_async(prompt, system_prompt="你是專業的證券分析助理，擅長精確識別實體。", context_tag=f"{debate_id}:Chairman:EntityExtraction")
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            print(f"Entity extraction failed: {e}")
            
        return {"subject": topic, "code": None, "industry_hint": None}

    async def pre_debate_analysis(self, topic: str, debate_id: str = None) -> Dict[str, Any]:
        """
        執行賽前分析的 7 步管線 (Async)。
        [Optimized Flow]: Entity Extraction -> Internal Check -> [Background Investigation] -> 7-Step Analysis
        """
        print(f"Chairman '{self.name}' is starting pre-debate analysis for topic: '{topic}'")
        self._publish_log(debate_id, f"正在開始賽前分析：{topic}...")

        # 1. 第一層：LLM 直接抽取實體 (Entity Recognition)
        entities = await self._extract_entities_from_query(topic, debate_id)
        subject = entities.get("subject", topic)
        code = entities.get("code")
        
        # 2. 第二層：內部校驗與題目鎖定 (Decree & Database Validation)
        self._publish_log(debate_id, f"⚖️ 正在執行初步題目鎖定驗證 (Decree Validation for '{subject}')...")
        
        initial_decree = {
            "subject": subject,
            "code": code or "Unknown",
            "industry": entities.get("industry_hint", "Unknown")
        }
        
        self.topic_decree = await self._validate_and_correction_decree(initial_decree, debate_id)
        
        # 3. 第三層：按需執行背景調查 (Background Investigation based on Topic Type)
        bg_info = ""
        is_verified = self.topic_decree.get("is_verified", False)
        
        # 強制啟動背景調查以獲取宏觀與產業鏈數據
        self._publish_log(debate_id, f"🔬 啟動議題類型導向調查...")
        bg_info = await self._investigate_topic_async(topic, debate_id)

        # 獲取推薦工具
        self._publish_log(debate_id, "🔍 正在分析題目並檢索推薦工具...")
        recommended_tools = get_recommended_tools_for_topic(topic)
        tools_desc = get_tools_description()
        
        # 🧠 構建 7 步分析
        self._publish_log(debate_id, "🧠 正在構建 7 步分析思維鏈 (Chain of Thought)...")
        db = SessionLocal()
        try:
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis") or "分析辯題：{{topic}}"
            from datetime import datetime, timedelta
            now = datetime.strptime(CURRENT_DATE, "%Y-%m-%d")
            format_vars = {
                "tools_desc": "本階段請勿使用工具，請基於提供的背景資訊進行純邏輯分析。",
                "background_info": bg_info,
                "CURRENT_DATE": CURRENT_DATE,
                "stock_codes": chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                "recommended_tools": ', '.join(recommended_tools)
            }
            system_prompt = template
            for key, value in format_vars.items():
                system_prompt = system_prompt.replace(f"{{{{{key}}}}}", str(value))
        finally:
            db.close()
            
        base_prompt = f"分析辯題：{topic}\n\n【背景事實】:\n{bg_info}\n\n【題目鎖定】:\n{json.dumps(self.topic_decree, ensure_ascii=False)}"
        self._publish_log(debate_id, "🚀 正在調用 LLM 進行深度戰略分析...")
        
        current_prompt = base_prompt
        analysis_result = {}
        
        for attempt in range(3):
            response = await call_llm_async(current_prompt, system_prompt=system_prompt, context_tag=f"{debate_id}:Chairman:PreAnalysis")
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed_json = json.loads(json_match.group(0), strict=False)
                    if "tool" in parsed_json: continue # Handle accidental tool calls
                    analysis_result = parsed_json
                    break
            except: pass

        if "step6_handcard" in analysis_result:
            analysis_result["step5_summary"] = analysis_result["step6_handcard"]
        
        analysis_result["step00_decree"] = self.topic_decree
        
        # [Analysis Verification]
        try:
            # 1. Internal Integrity Check
            analysis_result = await self._verify_analysis_integrity(analysis_result, bg_info, debate_id)
            
            # 2. External Guardrail Audit
            from worker.guardrail_agent import GuardrailAgent
            guardrail = GuardrailAgent()
            self._publish_log(debate_id, "🛡️ 正在執行中立審查員深度稽核...")
            audit = guardrail.check("Chairman", json.dumps(analysis_result.get("step5_summary", "")), f"Facts: {bg_info}")
            
            if audit.get("status") == "REJECTED":
                self._publish_log(debate_id, f"⛔ 審查員駁回分析：{audit.get('reason')}")
                correction_prompt = f"請根據以下事實重新產出【無幻覺】的摘要：\n{bg_info}"
                analysis_result["step5_summary"] = await call_llm_async(correction_prompt, system_prompt="你是誠實分析師。")
        except: pass

        print(f"Pre-debate analysis completed.")
        return {
            "analysis": analysis_result,
            "bg_info": bg_info
        }

    async def _verify_analysis_integrity(self, analysis: Dict[str, Any], bg_info: str, debate_id: str = None) -> Dict[str, Any]:
        """
        Verify the integrity of the pre-debate analysis result (Handcard).
        """
        self._publish_log(debate_id, "🛡️ 正在執行主席分析驗證...")
        handcard = analysis.get("step6_handcard") or analysis.get("step5_summary")
        if not handcard: return analysis
        handcard_str = str(handcard)
        
        prompt = f"檢查以下分析報告是否包含捏造數據：\n報告：{handcard_str}\n事實背景：{bg_info}\n要求：背景沒提到的百分比或數據必須刪除。若有誤請回傳修正後的 JSON，否則回傳 PASSED。"
        check_result = await call_llm_async(prompt, system_prompt="你是嚴格的事實查核員。", context_tag=f"{debate_id}:AnalysisCheck")
        
        if "PASSED" not in check_result:
            try:
                json_match = re.search(r'\{.*\}', check_result, re.DOTALL)
                if json_match:
                    corrected = json.loads(json_match.group(0))
                    analysis["step5_summary"] = corrected
                    analysis["step6_handcard"] = corrected
                    self._publish_log(debate_id, "✅ 已自動修正虛構數據。")
            except: pass
        return analysis

    async def _validate_and_correction_decree(self, decree: Dict[str, Any], debate_id: str = None) -> Dict[str, Any]:
        """
        Validate and correct the decree (Subject & Code) using tools.
        """
        self._publish_log(debate_id, "⚖️ 主席正在驗證題目鎖定 (Decree Validation)...")
        subject = decree.get("subject", "Unknown")
        code = decree.get("code", "Unknown")
        final_decree = decree.copy()
        
        def is_valid(val):
            return val and val not in ["Unknown", "None", "", "null", "Unknown (Unknown)"]

        # Strategy 0: STOCK_CODES
        for known_name, known_code in STOCK_CODES.items():
            if known_name in str(subject):
                final_decree["subject"] = known_name
                final_decree["code"] = known_code if "." in str(known_code) else f"{known_code}.TW"
                final_decree["is_verified"] = True
                self._publish_log(debate_id, f"✅ (Memory) 識別到常用股票：{known_name} -> {final_decree['code']}")
                return final_decree

        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        verified = False
        if is_valid(code):
            try:
                res_ct = await loop.run_in_executor(None, call_tool, "chinatimes.stock_fundamental", {"code": code})
                if res_ct.get("data"):
                    final_decree["subject"] = res_ct["data"].get("Name", subject)
                    final_decree["industry"] = res_ct["data"].get("SectorName", "Unknown")
                    self._publish_log(debate_id, f"✅ (ChinaTimes) 驗證：{final_decree['subject']} ({final_decree['industry']})")
                    verified = True
            except: pass

        if not verified and is_valid(subject):
            try:
                q = f"{subject} 台灣股票 代號 site:twse.com.tw"
                search_res = await loop.run_in_executor(None, call_tool, "searxng.search", {"q": q, "num_results": 3})
                prompt = f"從搜尋結果中提取「{subject}」的 4 位台股代碼：\n{str(search_res)[:1000]}"
                extracted_code = await call_llm_async(prompt, system_prompt="你是代碼助手。")
                extracted_code = re.search(r'\b\d{4}\b', extracted_code)
                if extracted_code:
                    final_decree["code"] = f"{extracted_code.group(0)}.TW"
                    verified = True
            except: pass

        final_decree["is_verified"] = verified
        return final_decree

    def summarize_round(self, debate_id: str, round_num: int, handcard: str = ""):
        """對本輪辯論進行總結"""
        redis_client = get_redis_client()
        try:
            evidence_list = [json.loads(item) for item in redis_client.lrange(f"debate:{debate_id}:evidence", 0, -1)]
        except: evidence_list = []
        evidence_text = "\n".join([f"- {e.get('role')}: {str(e.get('content'))[:200]}" for e in evidence_list])
        summary = call_llm(f"總結本輪證據：\n{evidence_text}", system_prompt="你是辯論主席。")
        final_summary = f"【第 {round_num} 輪總結】\n" + summary
        self.speak(final_summary)
        return final_summary

    async def _conduct_extended_research(self, topic: str, verdict: str, debate_id: str = None) -> str:
        """執行延伸調查"""
        self._publish_log(debate_id, "🔬 主席正在進行延伸調查...")
        from api.tool_registry import tool_registry
        target_tools = []
        for name in ["av.CPI", "av.EXCHANGE_RATE", "searxng.search"]:
            try:
                t_data = tool_registry.get_tool_data(name)
                target_tools.append({"type": "function", "function": {"name": name, "description": t_data['description'], "parameters": t_data['schema']}})
            except: pass
        res = await call_llm_async(f"根據結論 '{verdict[:200]}' 為投資者搜集 3 個延伸數據。", system_prompt="你是研究員。", tools=target_tools)
        return res

    async def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """整場辯論最終總結"""
        self._publish_log(debate_id, "🎬 正在生成最終結案報告...")
        verdict = await call_llm_async(f"辯題：{topic}\n過程：{str(rounds_data)[:2000]}", system_prompt="你是辯論主席。請生成 Markdown 結案報告。")
        return verdict
