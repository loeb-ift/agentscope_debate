from agentscope.agent import AgentBase
from typing import Dict, Any
import redis
import json
import re
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE
from api.prompt_service import PromptService
from api.database import SessionLocal

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
            default_prompt = f"""你是辯論賽的主席與分析師。你的任務是對辯題進行深度的賽前分析。
請嚴格按照以下步驟進行分析，並輸出結果：

步驟 1: 類型識別 (Type Classification)
請從以下維度分析：
1. 辯題類型（事實型/價值型/政策型）
2. 核心爭議領域（政治/經濟/社會/科技/倫理等）
3. 時空範疇（當代/歷史/未來，地域性/全球性）
4. 價值衝突類型（自由vs秩序、效率vs公平、個人vs集體等）

步驟 2: 核心要素提取 (Core Elements Extraction)
基於辯題類型分析，請識別：
1. 行動主體（Actor）：誰來執行？
2. 行動內容（Action）：具體做什麼？
3. 政策工具（Instrument）：用什麼方法/機制？
4. 目標群體（Target）：影響誰？
5. 預期目標（Goal）：達成什麼？
6. 隱含假設（Assumptions）：辯題預設了什麼前提？

步驟 3: 因果鏈建構 (Causal Chain Mapping)
請建構：
1. **正方因果鏈**：政策/行動 → 中間機制 → 預期效果（至少 3 條主要路徑）
2. **反方因果鏈**：政策/行動 → 副作用/障礙 → 負面後果（至少 3 條主要路徑）
3. **因果鏈強度評估**：每條鏈的證據強度（強/中/弱）
4. **關鍵斷點**：哪些環節最容易被質疑？

步驟 4: 子問題分解 (Sub-Questions Breakdown)
將辯題拆解為 5-8 個可驗證的關鍵子問題，涵蓋：
1. **可行性問題**（技術/資源/制度層面）
2. **效果問題**（是否達到預期目標）
3. **代價問題**（成本/副作用/機會成本）
4. **比較問題**（與替代方案相比如何）
5. **價值問題**（符合哪些價值優先級）

步驟 5: 資料蒐集戰略 (Research Strategy)
基於子問題，設計資料蒐集計畫：
1. **優先級排序**：哪些問題最關鍵？（前 3 項）
2. **資訊來源**：學術證據、案例研究、統計數據、專家意見
3. **搜索關鍵詞**：中英文關鍵詞組合
4. **時效性要求**：需要最新數據的問題 vs 可用歷史數據

步驟 6: 主席手卡 Prompt 生成
基於前述分析，生成主席專用的完整手卡：
【辯論基礎資訊】、
【正方論證架構】（主線 1-3，每條包含：論點 → 機制 → 證據）、
【反方論證架構】（主線 1-3，每條包含：論點 → 機制 → 證據）、
【關鍵交鋒點】（爭議點、雙方立場、判準）、
【數據與案例庫】（關鍵統計、成功/失敗案例）、
【主席引導問題庫】（10-15 題）、
【時間管理建議】

步驟 7: 工具策略映射 (Tool Strategy Mapping)
請根據「資料蒐集戰略」中的需求，從下方【可用工具列表】中選擇最精準的工具。
**注意**：TEJ 工具提供了非常詳細的欄位說明（Schema），請務必根據你需要的具體欄位（如「毛利率」、「存貨週轉率」）來選擇對應的工具，而不僅僅是看工具名稱。

【工具使用決策樹】
- IF 需要最新數據（2024 後） → web_search
- IF 需要台灣上市櫃公司具體財務指標（如月營收、EPS） → 優先查閱 TEJ 工具 Schema
- IF 需要完整文章/報告 → web_fetch
- IF 需要學術權威性 → 搜索 .edu/.gov 域名

【結果存儲建議】

{{tools_desc}}

**重要常數**：
{{stock_codes}}
- 當前日期：{{current_date}}

**針對此辯題的推薦工具**：{{recommended_tools}}

請務必使用「繁體中文」進行回答。

請以 JSON 格式輸出，包含以下欄位：
{{
    "step1_type": "...",
    "step2_elements": "...",
    "step3_causal_chain": "...",
    "step4_sub_questions": "...",
    "step5_research_strategy": "...",
    "step6_handcard": "...",
    "step7_tool_strategy": "..."
}}
"""
            template = PromptService.get_prompt(db, "chairman.pre_debate_analysis", default=default_prompt)
            # Fill dynamic variables
            system_prompt = template.format(
                tools_desc=tools_desc,
                stock_codes=chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()]),
                current_date=CURRENT_DATE,
                recommended_tools=', '.join(recommended_tools)
            )
        finally:
            db.close()
        prompt = f"請對以下辯題進行分析：{topic}"
        
        response = call_llm(prompt, system_prompt=system_prompt)
        
        try:
            # 使用 Regex 提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # 嘗試修復常見的 JSON 格式錯誤 (如未轉義的換行符)
                try:
                    analysis_result = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # 如果 strict=False 仍然失敗，嘗試手動替換換行符
                    # 這是一個簡單的啟發式替換，將不在引號外的換行符替換為 \n
                    # 但對於複雜的嵌套 JSON 可能不夠完美
                    fixed_json_str = json_str.replace('\n', '\\n')
                    analysis_result = json.loads(fixed_json_str, strict=False)
            else:
                raise ValueError("No JSON object found in response")
            
            # 為了兼容舊代碼，將 step6_handcard 映射為 step5_summary (因為 debate_cycle.py 使用此 key)
            if "step6_handcard" in analysis_result:
                analysis_result["step5_summary"] = analysis_result["step6_handcard"]
            elif analysis_result.get("step5_summary") is None: # Only if neither handcard nor summary exists
                # 嘗試從其他欄位構建摘要
                summary_parts = []
                if "step1_type" in analysis_result:
                    summary_parts.append(f"題型：{analysis_result['step1_type']}")
                if "step2_elements" in analysis_result:
                    summary_parts.append(f"關鍵要素：{analysis_result['step2_elements']}")
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
                "step1_type": "未識別",
                "step2_elements": "未提取",
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
        
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        evidence_key = f"debate:{debate_id}:evidence"
        
        # 獲取本輪累積的證據/工具調用
        evidence_list = [json.loads(item) for item in redis_client.lrange(evidence_key, 0, -1)]
        
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
        try:
            default_prompt = """你是辯論賽主席。你的任務是總結第 {round_num} 輪辯論。
請根據賽前分析的【主席手卡】進行評估：

{handcard}

請回答：
1. 本輪雙方是否觸及關鍵交鋒點？
2. 提出的證據是否有效支持了論點？
3. 下一輪辯論應該聚焦什麼問題？

請保持中立、專業，並給出具體引導。"""
            
            template = PromptService.get_prompt(db, "chairman.summarize_round", default=default_prompt)
            system_prompt = template.format(round_num=round_num, handcard=handcard)
        finally:
            db.close()

        user_prompt = f"""本輪收集到的證據與發言摘要：
{evidence_text}

請進行總結："""

        if not evidence_list:
            user_prompt += "\n(本輪未收集到具體證據工具調用)"

        summary = call_llm(user_prompt, system_prompt=system_prompt)
        
        prefix = f"【第 {round_num} 輪總結】\n"
        final_summary = prefix + summary
        self.speak(final_summary)
        
        # 清除本輪證據 (準備下一輪)
        redis_client.delete(evidence_key)
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
            default_prompt = """你是辯論賽主席。辯論已經結束。
你的任務是根據賽前分析的【主席手卡】以及整場辯論的過程，做出最終的【有意義的結論】。

{handcard}

請在結論中包含：
1. 勝負判定（或優勢方判定），基於邏輯與證據強度。
2. 核心觀點梳理：雙方最強的論點是什麼？
3. 價值昇華：這場辯論帶給我們什麼啟示？

請務必保持客觀、公正、深度。"""
            template = PromptService.get_prompt(db, "chairman.summarize_debate", default=default_prompt)
            system_prompt = template.format(handcard=handcard)
        finally:
            db.close()

        user_prompt = f"""整場辯論記錄摘要：
{summary_text}

請進行最終總結："""

        final_conclusion = call_llm(user_prompt, system_prompt=system_prompt)
        
        self.speak(f"【最終總結】\n{final_conclusion}")
        return final_conclusion