import json
import os
from typing import Dict, Any, List

# 模擬 ReMe Long Term Memory 的行為
# 使用 JSON 文件作為簡單的持久化存儲

MEMORY_DIR = "data/memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

class BaseLongTermMemory:
    def __init__(self, name: str):
        self.name = name
        self.file_path = os.path.join(MEMORY_DIR, f"{name}.json")
        self.data = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def __enter__(self):
        # 模擬 Context Manager 初始化資源
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 模擬資源清理與自動保存
        self._save()

class ReMePersonalLongTermMemory(BaseLongTermMemory):
    """
    管理用戶/Agent特定的事實與偏好。
    """
    def __init__(self):
        super().__init__("personal_ltm")

    def retrieve(self, agent_name: str) -> str:
        # 簡單檢索：查找與該 Agent 相關的記憶
        relevant = [item['content'] for item in self.data if item.get('agent') == agent_name]
        return "\n".join(relevant)

    def record(self, agent_name: str, content: str):
        self.data.append({
            "agent": agent_name,
            "content": content,
            "timestamp": "iso-timestamp"
        })

class ReMeTaskLongTermMemory(BaseLongTermMemory):
    """
    存儲與任務相關的經驗（如辯論主題與結果）。
    """
    def __init__(self):
        super().__init__("task_ltm")

    def retrieve_similar_tasks(self, topic: str) -> str:
        # 模擬語義檢索 (這裡用簡單的關鍵詞匹配代替)
        relevant = []
        for item in self.data:
            if any(word in item['topic'] for word in topic.split()):
                relevant.append(f"Topic: {item['topic']}, Outcome: {item['conclusion']}")
        return "\n".join(relevant[:3]) # 返回最近 3 條

    def record(self, topic: str, conclusion: str, score: float = None):
        self.data.append({
            "topic": topic,
            "conclusion": conclusion,
            "score": score
        })

class ReMeToolLongTermMemory(BaseLongTermMemory):
    """
    記錄工具使用模式，生成工具調用指南。
    """
    def __init__(self):
        super().__init__("tool_ltm")

    def retrieve(self, query: str) -> str:
        # 檢索相關的工具使用範例
        # 模擬：如果 query 包含 "股價"，返回 TEJ 使用範例
        examples = []
        for item in self.data:
            if item.get('success'):
                examples.append(f"Task: {item.get('intent')} -> Tool: {item.get('tool')} Params: {item.get('params')}")
        return "\n".join(examples[-5:]) # 返回最近 5 個成功範例

    def record(self, intent: str, tool_name: str, params: Dict, result: Any, success: bool):
        self.data.append({
            "intent": intent,
            "tool": tool_name,
            "params": params,
            "success": success,
            "result_preview": str(result)[:100]
        })