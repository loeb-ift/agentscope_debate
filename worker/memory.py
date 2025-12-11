import json
import os
import asyncio
import logging
from typing import Dict, Any, List
from api.vector_store import VectorStore
from api.redis_client import get_redis_client
import time
import hashlib

logger = logging.getLogger(__name__)

# 模擬 ReMe Long Term Memory 的行為
# 使用 JSON 文件作為簡單的持久化存儲

MEMORY_DIR = "data/memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

class HippocampalMemory:
    """
    海馬體記憶系統 (Hippocampal Memory Architecture)
    
    整合短期記憶 (Working Memory) 與長期記憶 (Long-term Memory)，
    並提供多維度索引檢索功能。
    """
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        self.redis = get_redis_client()
        self.wm_prefix = f"memory:working:{debate_id}"
        self.ltm_collection = f"hippocampus_{debate_id}"
        self.consolidation_threshold = 2 # Access count required for consolidation
        self.volatile_tools = [
            "tej.stock_price", "tej.fund_nav", "tej.options_daily_trading", "tej.futures_data",
            "yfinance.stock_price", "searxng.search", "duckduckgo.search"
        ]
        
    def _get_wm_key(self, tool: str, params: dict) -> str:
        # Generate deterministic key based on tool and sorted params
        param_str = json.dumps(params, sort_keys=True)
        h = hashlib.md5(f"{tool}:{param_str}".encode()).hexdigest()
        return f"{self.wm_prefix}:{h}"

    async def store(self, agent_id: str, tool: str, params: dict, result: Any):
        """
        感知層入口：將工具執行結果存入工作記憶 (Working Memory)。
        """
        key = self._get_wm_key(tool, params)
        timestamp = time.time()
        
        # Structure for Working Memory
        memory_item = {
            "id": key,
            "agent_id": agent_id,
            "tool": tool,
            "params": params,
            "result": result, # Assuming result is JSON serializable
            "timestamp": timestamp,
            "created_at_iso": datetime.fromtimestamp(timestamp).isoformat(),
            "access_count": 1,
            "consolidated": False
        }
        
        # Store in Redis with TTL (e.g., 24 hours for short-term context)
        # Using hash to store metadata, but for simplicity storing full JSON
        # Check if exists to update access count
        existing = self.redis.get(key)
        if existing:
            data = json.loads(existing)
            data["access_count"] += 1
            data["last_accessed"] = timestamp
            # Result might be same, but we update metadata
            memory_item = data
        
        self.redis.set(key, json.dumps(memory_item, default=str), ex=86400)
        
        # If access count is high enough, we might trigger immediate consolidation or wait for batch
        # For now, we just store. Consolidation happens periodically.
        
        logger.info(f"Hippocampus stored WM: {tool} (Access: {memory_item['access_count']})")

    async def retrieve_working_memory(self, tool: str, params: dict) -> Optional[Dict]:
        """
        從工作記憶檢索 (Exact Match)。
        """
        key = self._get_wm_key(tool, params)
        data = self.redis.get(key)
        if data:
            item = json.loads(data)
            # Update access stats
            item["access_count"] += 1
            item["last_accessed"] = time.time()
            self.redis.set(key, json.dumps(item), ex=86400)
            return item
        return None

    async def consolidate(self):
        """
        記憶鞏固：將高價值的工作記憶轉移到長期記憶。
        """
        # Scan all keys in working memory
        cursor = '0'
        while cursor != 0:
            cursor, keys = self.redis.scan(cursor=cursor, match=f"{self.wm_prefix}:*", count=100)
            if not keys:
                break
                
            for key in keys:
                data_str = self.redis.get(key)
                if not data_str: continue
                
                item = json.loads(data_str)
                
                # Consolidation Criteria
                if not item.get("consolidated") and item.get("access_count", 0) >= self.consolidation_threshold:
                    await self._save_to_ltm(item)
                    
                    # Mark as consolidated in WM
                    item["consolidated"] = True
                    self.redis.set(key, json.dumps(item), ex=86400)
                    logger.info(f"Consolidated memory: {item['tool']}")

    async def _save_to_ltm(self, item: Dict):
        """
        寫入長期記憶 (Vector Store)。
        建立多維索引: Semantic, Temporal, Source.
        """
        # Construct content for embedding
        # We summarize the tool input/output
        content_text = f"Tool: {item['tool']}\nParams: {item['params']}\nResult Summary: {str(item['result'])[:500]}"
        
        is_volatile = item["tool"] in self.volatile_tools
        
        metadata = {
            "timestamp": item["timestamp"],
            "date_str": item["created_at_iso"][:10],
            "agent_id": item["agent_id"],
            "tool": item["tool"],
            "type": "tool_result",
            "access_count": item["access_count"],
            "is_volatile": is_volatile
        }
        
        # Add to Qdrant
        await VectorStore.add_texts(
            collection_name=self.ltm_collection,
            texts=[content_text],
            metadatas=[metadata]
        )

    async def search_shared_memory(self, query: str, limit: int = 5, filter_tool: str = None) -> str:
        """
        語義檢索共享記憶 (LTM)。
        """
        filters = {}
        if filter_tool:
            filters["tool"] = filter_tool
            
        results = await VectorStore.search(
            collection_name=self.ltm_collection,
            query=query,
            limit=limit,
            filter_conditions=filters
        )
        
        if not results:
            return "No relevant memories found in shared hippocampus."
            
        formatted = []
        now = time.time()
        for r in results:
            # Check for staleness of volatile data
            is_volatile = r.get("is_volatile", False)
            timestamp = r.get("timestamp", 0)
            age_days = (now - timestamp) / 86400
            
            warning = ""
            if is_volatile and age_days > 3:
                warning = " ⚠️ [Historical Snapshot - Check Date!]"
                
            formatted.append(f"- [{r.get('date_str')}{warning}] {r.get('agent_id')} used {r.get('tool')}:\n  {r.get('text')[:200]}...")
            
        return "\n".join(formatted)

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
        logger.warning("ReMeTaskLongTermMemory.retrieve_similar_tasks is not implemented in sync mode. Use retrieve_similar_tasks_async instead.")
        raise NotImplementedError("Use retrieve_similar_tasks_async instead of the sync method.")

    async def retrieve_similar_tasks_async(self, topic: str) -> str:
        results = await VectorStore.search(self.collection_name, topic, limit=3)
        relevant = []
        for item in results:
            relevant.append(f"Topic: {item.get('topic')}, Outcome: {item.get('conclusion')}")
        return "\n".join(relevant)

    def record(self, topic: str, conclusion: str, score: float = None):
        logger.warning("ReMeTaskLongTermMemory.record is not implemented in sync mode. Use record_async instead.")
        raise NotImplementedError("Use record_async instead of the sync method.")

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
        logger.warning("ReMeToolLongTermMemory.retrieve is not implemented in sync mode. Use retrieve_async instead.")
        raise NotImplementedError("Use retrieve_async instead of the sync method.")

    async def retrieve_async(self, query: str) -> str:
        # Retrieve successful tool usages similar to the query
        filter_cond = {"success": True}
        results = await VectorStore.search(self.collection_name, query, limit=5, filter_conditions=filter_cond)
        
        examples = []
        for item in results:
            examples.append(f"Task: {item.get('intent')} -> Tool: {item.get('tool')} Params: {item.get('params')}")
        return "\n".join(examples)

    def record(self, intent: str, tool_name: str, params: Dict, result: Any, success: bool):
        logger.warning("ReMeToolLongTermMemory.record is not implemented in sync mode. Use record_async instead.")
        raise NotImplementedError("Use record_async instead of the sync method.")

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
        """Sync wrapper is not supported; please use add_turn_async instead."""
        logger.warning("ReMeHistoryMemory.add_turn is not implemented in sync mode. Use add_turn_async instead.")
        raise NotImplementedError("Use add_turn_async instead of the sync method.")

    async def add_turn_async(self, role: str, content: str, round_num: int):
        text = f"[{role}] (Round {round_num}): {content}"
        metadata = {
            "role": role,
            "content": content,
            "round": round_num
        }
        await VectorStore.add_texts(self.collection_name, [text], [metadata])

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        logger.warning("ReMeHistoryMemory.retrieve is not implemented in sync mode. Use retrieve_async instead.")
        raise NotImplementedError("Use retrieve_async instead of the sync method.")

    async def retrieve_async(self, query: str, top_k: int = 3) -> List[Dict]:
        results = await VectorStore.search(self.collection_name, query, limit=top_k)
        return results