from agentscope.agent import AgentBase
from typing import Dict, Any
import redis
import json
from worker.llm_utils import call_llm
from worker.tool_config import get_tools_description, get_recommended_tools_for_topic, STOCK_CODES, CURRENT_DATE

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
        
        system_prompt = f"""你是辯論賽的主席與分析師。你的任務是對辯題進行深度的賽前分析。
請嚴格按照以下步驟進行分析，並輸出結果：

Step 1: 題型識別 (這是一個怎樣的問題？例如：事實性、政策性、價值性)
Step 2: 核心要素萃取 (有哪些東西和這個問題是強相關)
Step 3: 因果鏈建構 (例如：A -> B -> C)
Step 4: 子題拆解 (Sub-questions) (如果命題為真，關係鏈是什麼？有哪些子問題需要驗證？)
Step 5: 戰略分析總結 (給 Agent 的戰前情報摘要)
Step 6: 主席備註 (Chairman Notes) (將注入 Agent Prompt 的注意事項)
Step 7: 工具策略預覽 (Tool Strategy) (推薦使用的工具)

{tools_desc}

**重要常數**：
{chr(10).join([f"- {name}: {code}" for name, code in STOCK_CODES.items()])}
- 當前日期：{CURRENT_DATE}

**針對此辯題的推薦工具**：{', '.join(recommended_tools)}

請務必使用「繁體中文」進行回答。

請以 JSON 格式輸出，包含以下欄位：
{{
    "step1_type": "...",
    "step2_elements": "...",
    "step3_causal_chain": "...",
    "step4_sub_questions": "...",
    "step5_summary": "...",
    "step6_notes": "...",
    "step7_tools": "..."
}}
"""
        prompt = f"請對以下辯題進行分析：{topic}"
        
        response = call_llm(prompt, system_prompt=system_prompt)
        
        try:
            # 嘗試解析 JSON，如果 LLM 返回了 Markdown code block，需要處理
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            analysis_result = json.loads(response)
        except Exception as e:
            print(f"Error parsing analysis result: {e}. Raw response: {response}")
            # Fallback structure
            analysis_result = {
                "step1_type": "未識別",
                "step2_elements": "未提取",
                "step3_causal_chain": "未建構",
                "step4_sub_questions": "未拆解",
                "step5_summary": response, # 將原始回應作為總結
                "step6_notes": "請注意客觀事實。",
                "step7_tools": ", ".join(recommended_tools)
            }

        print(f"Pre-debate analysis completed.")
        return analysis_result

    def summarize_round(self, debate_id: str, round_num: int):
        """
        對本輪辯論進行總結。
        """
        print(f"Chairman '{self.name}' is summarizing round {round_num}.")
        
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        evidence_key = f"debate:{debate_id}:evidence"
        
        # 這裡應該要獲取本輪的所有發言紀錄，而不僅僅是證據
        # 但為了簡化，我們先假設證據就是發言的一部分
        
        evidence_list = [json.loads(item) for item in redis_client.lrange(evidence_key, 0, -1)]
        
        summary = f"本輪辯論結束，共收集到 {len(evidence_list)} 條證據。"
        self.speak(summary)
        
        # 清除本輪證據
        redis_client.delete(evidence_key)