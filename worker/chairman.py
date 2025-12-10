from agentscope.agent import AgentBase
from typing import Dict, Any
import json
import re
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal
from api.redis_client import get_redis_client

class Chairman(AgentBase):
    """
    主席智能體，負責主持辯論、賽前分析和賽後總結。
    """

    def __init__(self, name: str, **kwargs: Any):
        super().__init__()
        self.name = name

    def speak(self, content: str):
        """
        主席發言。
        """
        print(f"Chairman '{self.name}': {content}")

    def pre_debate_analysis(self, topic: str) -> Dict[str, Any]:
        """
        執行賽前分析的 7 步管線。
        """
        print(f"Chairman '{self.name}' is starting pre-debate analysis for topic: '{topic}'")

        # 獲取推薦工具
        recommended_tools = get_recommended_tools_for_topic(topic)
        tools_desc = get_tools_description()
        
        # 使用 PromptService 獲取 Prompt
        db = SessionLocal()
        try:
            # Note: Hardcoded prompt removed. We rely on PromptService to load from prompts/system/chairman_analysis.yaml
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis")
            
            if not template:
                print("CRITICAL WARNING: 'chairman.pre_debate_analysis' prompt not found in DB or Files.")
                # Minimal fallback to prevent crash, but strictly minimal as requested
                template = "請分析辯題：{{topic}}"

            from datetime import datetime, timedelta
            now = datetime.strptime(CURRENT_DATE, "%Y-%m-%d")
            current_quarter = (now.month - 1) // 3 + 1
            
            format_vars = {
                "tools_desc": tools_desc,
                "stock_codes": chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                "recommended_tools": ', '.join(recommended_tools),
                "CURRENT_DATE": CURRENT_DATE,
                "CURRENT_QUARTER": f"{now.year} Q{current_quarter}",
                "CURRENT_YEAR": now.year,
                "CURRENT_MONTH": now.month,
                "NEXT_YEAR": now.year + 1,
                "DATE_5_YEARS_AGO": (now - timedelta(days=365*5)).strftime("%Y-%m-%d"),
                "DATE_3_YEARS_AGO": (now - timedelta(days=365*3)).strftime("%Y-%m-%d"),
                "DATE_1_YEAR_AGO": (now - timedelta(days=365*1)).strftime("%Y-%m-%d"),
                "DATE_3_MONTHS_AGO": (now - timedelta(days=90)).strftime("%Y-%m-%d"),
                "DATE_3_MONTHS_FUTURE": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
                "DATE_1_YEAR_FUTURE": (now + timedelta(days=365*1)).strftime("%Y-%m-%d"),
                "DATE_3_YEARS_FUTURE": (now + timedelta(days=365*3)).strftime("%Y-%m-%d"),
                "DATE_5_YEARS_FUTURE": (now + timedelta(days=365*5)).strftime("%Y-%m-%d"),
            }
            
            system_prompt = template
            for key, value in format_vars.items():
                system_prompt = system_prompt.replace(f"{{{{{key}}}}}", str(value))
        finally:
            db.close()
            
        prompt = f"請對以下辯題進行分析：{topic}\n\n**務必僅返回有效的 JSON 格式，不要包含 Markdown 標記或其他文字。**"
        
        response = call_llm(prompt, system_prompt=system_prompt)
        
        try:
            # 嘗試提取 JSON (支援 Markdown code block)
            json_str = response
            # 1. 嘗試匹配 ```json ... ``` 或 ``` ... ```
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1)
            else:
                # 2. 嘗試匹配最外層的 { ... }
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
            
            # 嘗試解析 JSON
            try:
                analysis_result = json.loads(json_str, strict=False)
            except json.JSONDecodeError:
                # 嘗試修復常見錯誤: 未轉義的換行符
                fixed_json_str = json_str.replace('\n', '\\n')
                analysis_result = json.loads(fixed_json_str, strict=False)

            if not isinstance(analysis_result, dict):
                 raise ValueError("Parsed JSON is not a dictionary")

            
            # 為了兼容舊代碼，將 step6_handcard 映射為 step5_summary (因為 debate_cycle.py 使用此 key)
            if "step6_handcard" in analysis_result:
                analysis_result["step5_summary"] = analysis_result["step6_handcard"]
            elif analysis_result.get("step5_summary") is None: # Only if neither handcard nor summary exists
                # 嘗試從其他欄位構建摘要
                summary_parts = []
                if "step1_type_classification" in analysis_result:
                    summary_parts.append(f"題型：{analysis_result['step1_type_classification']}")
                elif "step1_type" in analysis_result: # Backward compatibility
                    summary_parts.append(f"題型：{analysis_result['step1_type']}")
                
                if "step0_5_region_positioning" in analysis_result:
                    region_info = analysis_result["step0_5_region_positioning"]
                    if isinstance(region_info, dict):
                        region = region_info.get("region", "Unknown")
                        summary_parts.append(f"區域定位：{region}")

                if "step00_company_identification" in analysis_result:
                    comp_info = analysis_result["step00_company_identification"]
                    if isinstance(comp_info, dict):
                        companies = comp_info.get("identified_companies", "None")
                        codes = comp_info.get("stock_codes", "None")
                        summary_parts.append(f"識別公司：{companies} ({codes})")

                if "step0_5_industry_identification" in analysis_result:
                    industry_info = analysis_result["step0_5_industry_identification"]
                    if isinstance(industry_info, dict):
                        domain = industry_info.get("industry_domain", "Unknown")
                        summary_parts.append(f"涉及產業：{domain}")
                        companies = industry_info.get("leading_companies", [])
                        if companies and isinstance(companies, list):
                            company_names = [c.get("name", "") for c in companies if isinstance(c, dict)]
                            summary_parts.append(f"龍頭企業：{', '.join(company_names)}")
                    
                if "step2_elements" in analysis_result: # Same key in new prompt? No, new is same step2_core_elements?
                    # Wait, prompt says: step2_core_elements. Old code: step2_elements.
                    summary_parts.append(f"關鍵要素：{analysis_result['step2_elements']}")
                elif "step2_core_elements" in analysis_result:
                    summary_parts.append(f"關鍵要素：{analysis_result['step2_core_elements']}")
                    
                if "step5_research_strategy" in analysis_result:
                    summary_parts.append(f"資料蒐集戰略：{analysis_result['step5_research_strategy']}")
                
                if summary_parts:
                    analysis_result["step5_summary"] = "\n".join(summary_parts)
                else:
                    print(f"WARNING: LLM Analysis JSON missing key fields. Keys found: {list(analysis_result.keys())}")
                    analysis_result["step5_summary"] = f"分析完成，但在提取摘要時遇到問題。完整回應如下：\n{json.dumps(analysis_result, ensure_ascii=False, indent=2)}"

        except Exception as e:
            print(f"Error parsing analysis result: {e}. Raw response: {response}")
            # Fallback structure
            analysis_result = {
                "step1_type_classification": "未識別",
                "step2_core_elements": "未提取",
                "step3_causal_chain": "未建構",
                "step4_sub_questions": "未拆解",
                "step5_research_strategy": "未規劃",
                "step6_handcard": response if response else "分析失敗，無法生成主席手卡。",
                "step7_tool_strategy": ", ".join(recommended_tools),
                "step5_summary": response if response else "分析失敗，無法生成摘要。" # 兼容性
            }

        # Debug: 確認 step5_summary 存在
        print(f"DEBUG: analysis_result keys: {list(analysis_result.keys())}")
        summary_value = analysis_result.get('step5_summary', 'KEY_NOT_FOUND')
        summary_preview = str(summary_value)[:200] if summary_value else "EMPTY"
        print(f"DEBUG: step5_summary value: {summary_preview}")
        
        print(f"Pre-debate analysis completed.")
        return analysis_result

    def summarize_round(self, debate_id: str, round_num: int, handcard: str = ""):
        """
        對本輪辯論進行總結，基於賽前手卡進行評估。
        """
        print(f"Chairman '{self.name}' is summarizing round {round_num}.")
        
        redis_client = get_redis_client()
        evidence_key = f"debate:{debate_id}:evidence"
        
        # 獲取本輪累積的證據/工具調用
        try:
            evidence_list = [json.loads(item) for item in redis_client.lrange(evidence_key, 0, -1)]
        except Exception as e:
            print(f"Error fetching evidence from Redis: {e}")
            evidence_list = []
        
        # 構建證據摘要 (應用簡單的緊湊化策略)
        compact_evidence = []
        for e in evidence_list:
            content = e.get('content', str(e))
            if len(content) > 500:
                content = content[:200] + "...(略)..." + content[-200:]
            compact_evidence.append(f"- {e.get('role', 'Unknown')}: {content}")
            
        evidence_text = "\n".join(compact_evidence)
        
        # 這裡理想情況下應該也要獲取本輪的發言內容 (需從 Redis log stream 或 DB 獲取)
        # 暫時依賴 evidence_list 作為代理，或者假設 debate_cycle 會傳入上下文
        
        db = SessionLocal()
        next_round = round_num + 1
        try:
            # Hardcoded prompt removed. Rely on prompts/system/chairman_summary.yaml
            template = PromptService.get_prompt(db, "chairman.summarize_round")
            if not template:
                print("WARNING: 'chairman.summarize_round' prompt not found.")
                template = "請總結本輪辯論。"
            system_prompt = template.format(round_num=round_num, handcard=handcard, next_round=next_round)
            
            # Load User Prompt
            user_template = PromptService.get_prompt(db, "chairman.summarize_round_user")
            if not user_template: user_template = "{evidence_text}"
            user_prompt = user_template.format(evidence_text=evidence_text)
        finally:
            db.close()

        if not evidence_list:
            user_prompt += "\n(本輪未收集到具體證據工具調用)"

        summary = call_llm(user_prompt, system_prompt=system_prompt)
        
        prefix = f"【第 {round_num} 輪總結】\n"
        final_summary = prefix + summary
        self.speak(final_summary)
        
        # 清除本輪證據 (準備下一輪)
        try:
            redis_client.delete(evidence_key)
        except Exception as e:
            print(f"Error clearing evidence key: {e}")
            
        return final_summary

    def summarize_debate(self, debate_id: str, topic: str, rounds_data: list, handcard: str = "") -> str:
        """
        對整場辯論進行最終總結。
        """
        print(f"Chairman '{self.name}' is making the final conclusion.")
        
        # 構建辯論摘要
        summary_text = f"辯題：{topic}\n\n"
        for round_data in rounds_data:
            summary_text += f"--- 第 {round_data['round']} 輪 ---\n"
            # 動態遍歷所有團隊的發言
            for key, value in round_data.items():
                if key.endswith("_content"):
                    side = key.replace("_content", "")
                    agent_name = round_data.get(f"{side}_agent", "Unknown")
                    summary_text += f"團隊 {side} ({agent_name}): {str(value)[:200]}...\n"
            
            summary_text += f"回合總結: {str(round_data.get('summary', ''))[:200]}...\n\n"
            
        db = SessionLocal()
        try:
            # Hardcoded prompt removed. Rely on prompts/system/chairman_summary.yaml
            template = PromptService.get_prompt(db, "chairman.summarize_debate")
            if not template:
                print("WARNING: 'chairman.summarize_debate' prompt not found.")
                template = "請總結整場辯論。"
                
            system_prompt = template.format(handcard=handcard)
            
            # Load User Prompt
            user_template = PromptService.get_prompt(db, "chairman.summarize_debate_user")
            if not user_template: user_template = "{summary_text}"
            user_prompt = user_template.format(summary_text=summary_text)
        finally:
            db.close()

        final_conclusion = call_llm(user_prompt, system_prompt=system_prompt)
        
        self.speak(f"【最終總結】\n{final_conclusion}")
        return final_conclusion