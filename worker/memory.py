import json
import os
import asyncio
from typing import Dict, Any, List
from api.vector_store import VectorStore

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
    存儲與任務相關的經驗（如辯論主題與結果）。(Vectorized)
    """
    def __init__(self):
        super().__init__("task_ltm")
        self.collection_name = "task_memory"

    def retrieve_similar_tasks(self, topic: str) -> str:
        """Sync wrapper for backward compatibility - returns empty or needs async handling"""
        return ""

    async def retrieve_similar_tasks_async(self, topic: str) -> str:
        results = await VectorStore.search(self.collection_name, topic, limit=3)
        relevant = []
        for item in results:
            relevant.append(f"Topic: {item.get('topic')}, Outcome: {item.get('conclusion')}")
        return "\n".join(relevant)

    def record(self, topic: str, conclusion: str, score: float = None):
        """Sync wrapper"""
        pass

    async def record_async(self, topic: str, conclusion: str, score: float = None):
        text = f"Topic: {topic}\nOutcome: {conclusion}"
        metadata = {
            "topic": topic,
            "conclusion": conclusion,
            "score": score
        }
        await VectorStore.add_texts(self.collection_name, [text], [metadata])

class ReMeToolLongTermMemory(BaseLongTermMemory):
    """
    記錄工具使用模式，生成工具調用指南。(Vectorized)
    """
    def __init__(self):
        super().__init__("tool_ltm")
        self.collection_name = "tool_memory"

    def retrieve(self, query: str) -> str:
        """Sync wrapper"""
        return ""

    async def retrieve_async(self, query: str) -> str:
        # Retrieve successful tool usages similar to the query
        filter_cond = {"success": True}
        results = await VectorStore.search(self.collection_name, query, limit=5, filter_conditions=filter_cond)
        
        examples = []
        for item in results:
            examples.append(f"Task: {item.get('intent')} -> Tool: {item.get('tool')} Params: {item.get('params')}")
        return "\n".join(examples)

    def record(self, intent: str, tool_name: str, params: Dict, result: Any, success: bool):
        """Sync wrapper"""
        pass

    async def record_async(self, intent: str, tool_name: str, params: Dict, result: Any, success: bool):
        text = f"Intent: {intent} -> Tool: {tool_name}"
        metadata = {
            "intent": intent,
            "tool": tool_name,
            "params": params,
            "success": success,
            "result_preview": str(result)[:100]
        }
        await VectorStore.add_texts(self.collection_name, [text], [metadata])

class ReMeHistoryMemory(BaseLongTermMemory):
    """
    RAG for Debate History using Qdrant.
    """
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        # We don't use file storage for this one, but Base needs it.
        super().__init__(f"history_rag_{debate_id}")
        self.collection_name = f"debate_{debate_id}"

    def add_turn(self, role: str, content: str, round_num: int):
        """Async add turn (needs loop)"""
        # Fire and forget / background task style?
        # Or just store in local buffer and flush async?
        # We rely on caller to be async or use a helper.
        # But this method signature is sync.
        # We'll use a helper to run in new loop if needed, or assume caller handles async.
        # Given the caller (debate_cycle) is async, we should expose async method.
        pass

    async def add_turn_async(self, role: str, content: str, round_num: int):
        text = f"[{role}] (Round {round_num}): {content}"
        metadata = {
            "role": role,
            "content": content,
            "round": round_num
        }
        await VectorStore.add_texts(self.collection_name, [text], [metadata])

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """Sync wrapper (not recommended for production but keeps interface)"""
        # This will fail in async loop.
        return []

    async def retrieve_async(self, query: str, top_k: int = 3) -> List[Dict]:
        results = await VectorStore.search(self.collection_name, query, limit=top_k)
        return results