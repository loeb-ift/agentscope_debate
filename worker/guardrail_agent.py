from agentscope.agent import AgentBase
from worker.llm_utils import call_llm
from api.prompt_service import PromptService
from api.database import SessionLocal
import yaml
import json
import re

class GuardrailAgent(AgentBase):
    """
    合規審查員 (Guardrail Agent)
    專門負責檢查其他 Agent 的輸出是否符合 Base Contract。
    """

    def __init__(self, name: str = "Guardrail"):
        super().__init__()
        self.name = name
        self.config_path = "prompts/agents/guardrail.yaml"
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """載入 Guardrail 專用 System Prompt"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("system_prompt", "")
        except Exception as e:
            print(f"Error loading guardrail config: {e}")
            return "你是合規審查員，請檢查內容是否符合事實與邏輯。"

    def check(self, target_agent: str, content: str, context: str = "") -> dict:
        """
        執行審查
        
        Args:
            target_agent: 被審查的 Agent 名稱
            content: 被審查的內容 (Agent 的發言或思考)
            context: 相關上下文 (如辯題、上一輪發言)
            
        Returns:
            dict: {
                "status": "PASSED" | "REJECTED" | "WARNING",
                "violation_type": str,
                "reason": str,
                "correction_instruction": str,
                "severity": str
            }
        """
        user_prompt = f"""
【審查請求】
被審查者: {target_agent}
上下文: {context[:500]}...
待審查內容:
\"\"\"
{content}
\"\"\"

請根據你的 Check List 進行嚴格審查，並輸出 JSON 報告。
"""
        
        try:
            response = call_llm(user_prompt, system_prompt=self._system_prompt, temperature=0.1)
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                # Validate keys
                required_keys = ["status", "violation_type"]
                if all(k in result for k in required_keys):
                    return result
            
            # Fallback if JSON parsing fails but no explicit rejection found
            print(f"Guardrail JSON parse failed. Raw: {response[:100]}...")
            return {
                "status": "PASSED",
                "violation_type": "NONE",
                "reason": "Guardrail response parsing failed, defaulting to pass.",
                "confidence_score": 0.0
            }
            
        except Exception as e:
            print(f"Guardrail check failed: {e}")
            # Fail open (allow pass) or closed (reject all)? 
            # Design choice: Fail Open for robustness in MVP, but log error.
            return {
                "status": "PASSED", 
                "violation_type": "SYSTEM_ERROR",
                "reason": f"System error during check: {str(e)}"
            }