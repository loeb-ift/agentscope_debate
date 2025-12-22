import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from api.vector_store import VectorStore
from api.redis_client import get_redis_client
import time
import hashlib
import random
from datetime import datetime, time as dtime, timedelta, timezone
from worker.tool_manager import tool_manager

logger = logging.getLogger(__name__)

# 模擬 ReMe Long Term Memory 的行為
# 使用 JSON 文件作為簡單的持久化存儲

MEMORY_DIR = "data/memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

class HippocampalMemory:
    """
    海馬迴記憶系統 (Hippocampal Memory Architecture)
    
    整合短期記憶 (Working Memory) 與長期記憶 (Long-term Memory)，
    並提供多維度索引檢索功能。
    """
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        self.redis = get_redis_client()
        self.wm_prefix = f"memory:working:{debate_id}"
        
        # [Phase 23] Global Memory Tier Logic
        # Macro tools (av.*, fred.*, worldbank.*) are stored in a GLOBAL collection
        # Company specific tools remain in the DEBATE-specific collection
        self.ltm_collection = f"hippocampus_{debate_id}"
        self.global_ltm_collection = "hippocampus_global_macro"
        
        self.consolidation_threshold = 5 # Increased from 2 to 5 to prevent junk consolidation
        
        # [Optimization Phase 5] Write Buffer for Qdrant
        self._ltm_buffer = []
        self.buffer_size = 10

        # [Observability Phase 6] Stats
        self.stats = {
            "wm_hits": 0,
            "wm_misses": 0,
            "ltm_writes": 0,
            "wm_evictions": 0
        }
        
    def _calculate_value_score(self, item: dict) -> float:
        """
        計算記憶真實價值分數 (0.0 ~ 1.0) - V2 Hybrid Logic
        Combines V1 metrics with V2 metadata (trust_level).
        """
        # 1. Base Logic (V1 Metrics)
        retrieved = max(1, item.get("retrieved_count", 1))
        adopted = item.get("adopted_count", 0)
        
        adoption_rate = min(1.0, adopted / retrieved)
        
        # Recency
        now = time.time()
        age_hours = (now - item.get("last_accessed", item["timestamp"])) / 3600
        recency_score = 1.0 / (1.0 + 0.05 * age_hours)
        
        # 2. V2 Trust Bonus
        trust_bonus = 0.0
        meta = item.get("metadata", {})
        trust_level = meta.get("trust_level", "unverified")
        
        if trust_level == "verified":
            trust_bonus = 0.2
        elif trust_level == "highly_trusted":
            trust_bonus = 0.4
        elif trust_level == "disputed":
            trust_bonus = -0.3
            
        # Calculate Score (Weighted)
        # Base (0.5 max) + Trust (0.4 max) + Recency (0.1 max)
        score = (adoption_rate * 0.5) + trust_bonus + (recency_score * 0.1)
        
        # Cap at 1.0, Floor at 0.0
        return max(0.0, min(1.0, score))

    def _calculate_importance(self, item: dict) -> float:
        """Wrapper for backward compatibility"""
        return self._calculate_value_score(item)

    async def mark_adopted(self, tool: str, params: dict):
        """Mark memory as adopted (used in decision)"""
        key = self._get_wm_key(tool, params)
        data = self.redis.get(key)
        if data:
            item = json.loads(data)
            item["adopted_count"] = item.get("adopted_count", 0) + 1
            
            # [Survival Time Extension]
            # If item is adopted, it proves value. Extend TTL to ensure it survives
            # long enough to be consolidated to LTM.
            # Minimum survival: 24 hours or config TTL, whichever is higher.
            base_ttl = self._get_ttl(tool)
            extended_ttl = max(base_ttl, 86400)
            
            self.redis.set(key, json.dumps(item), ex=extended_ttl)
            
    async def mark_outcome(self, tool: str, params: dict, success: bool):
        """Mark memory outcome (success/failure)"""
        key = self._get_wm_key(tool, params)
        data = self.redis.get(key)
        if data:
            item = json.loads(data)
            if success:
                item["success_count"] = item.get("success_count", 0) + 1
            else:
                item["misleading_count"] = item.get("misleading_count", 0) + 1
                
            ttl = self._get_ttl(tool)
            self.redis.set(key, json.dumps(item), ex=ttl)

    async def cleanup_working_memory(self, retention_threshold: float = 0.3):
        """
        主動清理機制 (Active Forgetfulness)
        移除重要性低於閾值的短期記憶。
        """
        cursor = '0'
        removed_count = 0
        
        while cursor != 0:
            cursor, keys = self.redis.scan(cursor=cursor, match=f"{self.wm_prefix}:*", count=100)
            if not keys: break
            
            for key in keys:
                if key.endswith(":access"): continue
                
                data_str = self.redis.get(key)
                if not data_str: continue
                
                try:
                    item = json.loads(data_str)
                    # Sync access count
                    access_key = f"{key}:access"
                    item["access_count"] = int(self.redis.get(access_key) or 0)
                    
                    importance = self._calculate_importance(item)
                    
                    if importance < retention_threshold:
                        self.redis.delete(key)
                        self.redis.delete(access_key)
                        removed_count += 1
                        logger.debug(f"Hippocampus cleaned up low importance item: {key} (Score: {importance:.2f})")
                        
                except Exception as e:
                    logger.warning(f"Error during memory cleanup for {key}: {e}")
                    
        if removed_count > 0:
            self.stats["wm_evictions"] += removed_count
            logger.info(f"Hippocampus Active Cleanup: Removed {removed_count} items.")

    def _normalize_params(self, tool_name: str, params: dict) -> dict:
        """
        Normalize parameters for cache consistency:
        1. Resolve aliases (e.g. q -> query, ticker -> coid)
        2. Remove unknown parameters based on schema
        3. Soft align dates
        4. Sort keys (implicitly handled by json.dumps with sort_keys=True later)
        """
        try:
            # 1. Get Schema
            # Use lazy import to avoid circular dependency with api.tool_registry
            from api.tool_registry import tool_registry
            tool_data = tool_registry.get_tool_data(tool_name, version="v1")
            schema = tool_data.get("schema", {})
            properties = schema.get("properties", {}) if schema else {}
            
            # Map of standard aliases to canonical names
            # This helps cache hit rate when agents use synonyms
            alias_map = {
                "q": "query",
                "keyword": "query",
                "id": "coid",
                "company_id": "coid",
                "ticker": "coid",
                "symbol": "coid"
            }

            # Start with filtering and normalizing params
            normalized = {}
            
            for k, v in params.items():
                # Resolve alias if target exists in schema
                canonical_k = k
                if k in alias_map and alias_map[k] in properties:
                    canonical_k = alias_map[k]
                elif k in alias_map and tool_name.startswith("tej.") and alias_map[k] == "coid":
                     from api.config import Config
                     if Config.ENABLE_TEJ_TOOLS:
                         # Force coid for TEJ tools only when TEJ is enabled
                         canonical_k = "coid"
                     else:
                         canonical_k = alias_map[k]

                # [Governance] TEJ Disable Filter
                from api.config import Config
                if not Config.ENABLE_TEJ_TOOLS and tool_name.startswith("tej."):
                     continue # Skip indexing TEJ data if disabled

                # Filter unknown params
                if not properties or canonical_k in properties:
                    normalized[canonical_k] = v
                # Allow standard options
                elif canonical_k in ["limit", "offset", "opts.limit", "opts.offset"]:
                    normalized[canonical_k] = v
                # Keep 'limit' if it was mapped from something else
                elif k in ["limit", "opts.limit"]:
                     normalized["limit"] = v

            # 3. Soft Date Alignment
            # If start_date/end_date exist and span > 30 days, align to month start/end
            if "start_date" in normalized and "end_date" in normalized:
                try:
                    s_str = str(normalized["start_date"])
                    e_str = str(normalized["end_date"])
                    
                    # Basic YYYY-MM-DD check
                    if len(s_str) >= 10 and len(e_str) >= 10:
                        s_dt = datetime.strptime(s_str[:10], "%Y-%m-%d")
                        e_dt = datetime.strptime(e_str[:10], "%Y-%m-%d")
                        
                        delta_days = (e_dt - s_dt).days
                        
                        # Soft Alignment Rule: If range > 32 days, align to month boundaries
                        # This increases cache hit rate for "yearly" or "quarterly" queries that might differ by few days
                        if delta_days > 32:
                            # Snap start to 1st of month
                            s_new = s_dt.replace(day=1)
                            
                            # Snap end to last day of month (approx)
                            # Logic: Move to 1st of next month, then subtract 1 day
                            # Handle December
                            if e_dt.month == 12:
                                next_month = e_dt.replace(year=e_dt.year+1, month=1, day=1)
                            else:
                                next_month = e_dt.replace(month=e_dt.month+1, day=1)
                            e_new = next_month - timedelta(days=1)
                            
                            normalized["start_date"] = s_new.strftime("%Y-%m-%d")
                            normalized["end_date"] = e_new.strftime("%Y-%m-%d")
                            # logger.debug(f"Date aligned: {s_str}->{normalized['start_date']}, {e_str}->{normalized['end_date']}")
                            
                except ValueError:
                    pass # Date parse failed, keep original

            return normalized
        except Exception as e:
            logger.warning(f"Param normalization failed for {tool_name}: {e}")
            return params

    def _get_wm_key(self, tool: str, params: dict) -> str:
        # Normalize params first
        norm_params = self._normalize_params(tool, params)
        
        # Generate deterministic key based on tool and sorted params
        # Use 'v7' salt to invalidate old non-normalized cache (Aliases update)
        param_str = json.dumps(norm_params, sort_keys=True)
        h = hashlib.md5(f"{tool}:v7:{param_str}".encode()).hexdigest()
        return f"{self.wm_prefix}:{h}"

    def _get_ttl(self, tool: str) -> int:
        """Calculate Dynamic TTL using Tool Manager"""
        return tool_manager.get_ttl(tool)

    async def store(self, agent_id: str, tool: str, params: dict, result: Any):
        """
        感知層入口：將工具執行結果存入 Evidence Lifecycle System (取代單純 Redis)。
        Flow:
        1. Lifecycle.ingest (Create DRAFT)
        2. Lifecycle.verify (DRAFT -> VERIFIED/QUARANTINE)
        3. If Verified, cache in Redis (Hot Tier)
        """
        start = time.time()
        
        # [Lifecycle Integration]
        # Lazy load due to circular imports or initialization context
        from worker.evidence_lifecycle import EvidenceLifecycle
        lc = EvidenceLifecycle(self.debate_id)
        
        # 1. Ingest
        doc = lc.ingest(agent_id, tool, params, result)
        
        # 2. Verify (Immediate Sync Verification for now)
        # In a real async pipeline, this might be a separate task.
        doc = lc.verify(doc.id)
        
        if doc.status == "QUARANTINE":
            logger.warning(f"Hippocampus: Evidence {doc.id} quarantined. Reason: {doc.verification_log[-1].get('reason')}")
            # Do NOT cache in Hot Tier (Redis) to avoid pollution
            return

        # 3. Cache in Redis (Hot Tier) if Verified
        # We still use Redis for fast retrieval by Agent, but now it's backed by DB.
        
        key = self._get_wm_key(tool, params)
        timestamp = time.time()
        
        # Structure - Add Evidence ID
        memory_item = {
            "id": key,
            "evidence_id": doc.id, # Link to SSOT
            "agent_id": agent_id,
            "tool": tool,
            "params": params,
            "result": result, # We still keep content in Redis for speed
            "timestamp": timestamp,
            "created_at_iso": datetime.fromtimestamp(timestamp).isoformat(),
            # Metrics V2
            "metadata": {
                "trust_level": "verified", # Confirmed by Lifecycle
                "verification_history": doc.verification_log,
                "scores": {
                    "base": 50,
                    "bonus_verification": 20, # Bonus for passing Lifecycle
                    "total": 70
                },
                "usage_stats": {
                    "retrieved": 1,
                    "adopted": 0,
                }
            },
            "retrieved_count": 1,
            "adopted_count": 0,
            "consolidated": False
        }
        
        # Cache with TTL
        ttl = self._get_ttl(tool)
        self.redis.set(key, json.dumps(memory_item, default=str), ex=ttl)
        
        # Access Count
        access_key = f"{key}:access"
        new_count = self.redis.incr(access_key)
        self.redis.expire(access_key, ttl)
        
        elapsed = time.time() - start
        logger.info(f"Hippocampus stored Evidence {doc.id} (Status: {doc.status}) in {elapsed:.4f}s")

    async def retrieve_working_memory(self, tool: str, params: dict) -> Optional[Dict]:
        """
        從工作記憶檢索 (Exact Match)。
        """
        start = time.time()
        key = self._get_wm_key(tool, params)
        data = self.redis.get(key)
        elapsed = time.time() - start
        
        if data:
            item = json.loads(data)
            
            # [Fix 2] Atomic Increment Access Count
            access_key = f"{key}:access"
            new_count = self.redis.incr(access_key)
            
            # Update Item Metrics
            item["access_count"] = new_count
            item["retrieved_count"] = item.get("retrieved_count", 0) + 1
            item["last_accessed"] = time.time()
            
            # Save back updated metrics (Not fully atomic but good enough for stats)
            self.redis.set(key, json.dumps(item), ex=self._get_ttl(tool))
            
            # Refresh TTL on access (Sliding Window)
            ttl = self._get_ttl(tool)
            self.redis.expire(key, ttl)
            self.redis.expire(access_key, ttl)
            
            # Inject Freshness Metadata into Result if possible
            if isinstance(item.get("result"), dict):
                age = time.time() - item["timestamp"]
                tool_conf = tool_manager.get_tool_config(tool)
                is_volatile = tool_conf.lifecycle in ["realtime", "intraday"]
                
                item["result"]["_cache_meta"] = {
                    "source": "hippocampus_cache",
                    "age_seconds": int(age),
                    "created_at": item["created_at_iso"],
                    "is_stale": age > 300 and is_volatile
                }

            self.stats["wm_hits"] += 1
            
            # [Optimization] Calculate importance for logging
            importance = self._calculate_importance(item)
            logger.info(f"Hippocampus WM HIT: {tool} (Access: {new_count}, Imp: {importance:.2f}) in {elapsed:.4f}s")
            return item
        
        self.stats["wm_misses"] += 1
        logger.info(f"Hippocampus WM MISS: {tool} in {elapsed:.4f}s")
        return None

    async def consolidate(self):
        """
        記憶鞏固：將高價值的工作記憶轉移到長期記憶。
        """
        # [Optimization] First run active cleanup to remove low-value noise
        await self.cleanup_working_memory()

        # Scan all keys in working memory
        cursor = '0'
        while cursor != 0:
            cursor, keys = self.redis.scan(cursor=cursor, match=f"{self.wm_prefix}:*", count=100)
            if not keys:
                break
                
            for key in keys:
                # Skip access counter keys
                if key.endswith(":access"):
                    continue
                    
                data_str = self.redis.get(key)
                if not data_str: continue
                
                try:
                    item = json.loads(data_str)
                except:
                    continue
                
                # Get Access Count from separate key
                access_key = f"{key}:access"
                access_count = int(self.redis.get(access_key) or 0)
                item["access_count"] = access_count
                
                # [Optimization] Use Importance Score
                importance = self._calculate_importance(item)
                
                # Consolidation Criteria
                # 1. Importance Score Threshold (instead of just access count)
                # 2. Permission check (allow_ltm) via Tool Manager
                # 3. Quality Gate
                result_str = str(item.get("result", ""))
                is_error = "error" in result_str.lower() or "traceback" in result_str.lower()
                
                should_consolidate = tool_manager.should_consolidate(item["tool"])
                
                # Threshold for LTM is higher than simple retention (e.g., 0.6)
                if (not item.get("consolidated") and
                    importance >= 0.6 and
                    should_consolidate and
                    not is_error):
                    
                    await self._buffer_ltm_item(item)
                    
                    # Mark as consolidated in WM
                    item["consolidated"] = True
                    ttl = self._get_ttl(item["tool"])
                    self.redis.set(key, json.dumps(item), ex=ttl)
                    logger.info(f"Consolidated memory (buffered): {item['tool']} (Imp: {importance:.2f})")
        
        # Flush remaining items in buffer after scan
        await self._flush_ltm_buffer()

    def feedback_correction(self, debate_id: str, feedback_text: str):
        """
        [Stub] 反饋修正機制
        當收到用戶或系統反饋（如「數據錯誤」）時，用於標記或修正相關記憶。
        
        Args:
            debate_id: 關聯的辯論 ID
            feedback_text: 反饋內容
        """
        # TODO: Implement semantic search in LTM to find memories matching feedback_text
        # and mark them as 'disputed' or lower their score.
        logger.info(f"Received memory feedback for {debate_id}: {feedback_text}")

    async def _buffer_ltm_item(self, item: Dict):
        """Buffer item for LTM write"""
        content_text = f"Tool: {item['tool']}\nParams: {item['params']}\nResult Summary: {str(item['result'])[:500]}"
        
        tool_conf = tool_manager.get_tool_config(item["tool"])
        is_volatile = tool_conf.lifecycle in ["realtime", "intraday"]
        
        metadata = {
            "timestamp": item["timestamp"],
            "date_str": item["created_at_iso"][:10],
            "agent_id": item["agent_id"],
            "tool": item["tool"],
            "type": "tool_result",
            "access_count": item["access_count"],
            "is_volatile": is_volatile
        }
        
        self._ltm_buffer.append((content_text, metadata))
        
        if len(self._ltm_buffer) >= self.buffer_size:
            await self._flush_ltm_buffer()

    async def _flush_ltm_buffer(self):
        """Flush the Qdrant buffer"""
        if not self._ltm_buffer:
            return
            
        # [Phase 23] Route based on tool type
        global_items = [x for x in self._ltm_buffer if any(p in x[1].get('tool', '') for p in ['av.', 'fred.', 'worldbank.'])]
        local_items = [x for x in self._ltm_buffer if x not in global_items]
        
        async def _add_to_vstore(collection, items):
            if not items: return
            texts = [x[0] for x in items]
            metadatas = [x[1] for x in items]
            try:
                await VectorStore.add_texts(
                    collection_name=collection,
                    texts=texts,
                    metadatas=metadatas
                )
                self.stats["ltm_writes"] += len(texts)
                logger.info(f"Hippocampus flushed {len(texts)} items to {collection}.")
            except Exception as e:
                logger.error(f"Failed to flush Hippocampus buffer to {collection}: {e}")

        await _add_to_vstore(self.global_ltm_collection, global_items)
        await _add_to_vstore(self.ltm_collection, local_items)
            
        self._ltm_buffer.clear()

    async def _save_to_ltm(self, item: Dict):
        """
        Legacy single-item write (Wrapper around buffer for compatibility if needed directly)
        """
        await self._buffer_ltm_item(item)
        await self._flush_ltm_buffer()

    async def search_shared_memory(self, query: str, limit: int = 5, filter_tool: str = None, filter_coid: str = None) -> str:
        """
        語義檢索共享記憶。同時檢索「場次特定」與「全局宏觀」兩個 Tier。
        加入 [Phase 26] Strict Metadata Filter 防止跨公司污染。
        """
        from api.config import Config
        
        filters = {}
        if filter_tool:
            filters["tool"] = filter_tool
        if filter_coid:
            # 強制過濾特定公司代碼，防止台積電數據混入敦陽辯論
            filters["coid"] = filter_coid
            
        # 1. Search Local Debate Memory
        local_results = await VectorStore.search(
            collection_name=self.ltm_collection,
            query=query,
            limit=limit,
            filter_conditions=filters
        )
        
        # 2. Search Global Macro Memory (Cross-debate)
        # Macro 數據通常不帶 coid，所以不套用 filter_coid 以便共享
        global_results = await VectorStore.search(
            collection_name=self.global_ltm_collection,
            query=query,
            limit=limit,
            filter_conditions={k: v for k, v in filters.items() if k != "coid"}
        )
        
        results = local_results + global_results
        
        if not results:
            return "No relevant memories found in shared hippocampus."
            
        formatted = []
        now = time.time()
        for r in results:
            # [Governance] TEJ Filter for Retrieval
            tool_used = r.get("tool", "")
            if not Config.ENABLE_TEJ_TOOLS and tool_used.startswith("tej."):
                 continue
                 
            # [Phase 26 Security] Double check coid mismatch in results (Extra guard)
            res_coid = r.get("coid")
            if filter_coid and res_coid and str(res_coid) != str(filter_coid):
                continue # Skip mismatched company data

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
        # [Optimization] Batch Buffer
        self._buffer: List[tuple[str, dict]] = [] # list of (text, metadata)
        self.buffer_size = 5

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

    async def flush(self):
        """Flush buffer to VectorStore"""
        if not self._buffer:
            return
            
        texts = [item[0] for item in self._buffer]
        metadatas = [item[1] for item in self._buffer]
        
        if hasattr(self, 'collection_name'):
             await VectorStore.add_texts(self.collection_name, texts, metadatas)
             logger.info(f"Flushed {len(texts)} items to {self.collection_name}")
             
        self._buffer.clear()

    def __enter__(self):
        # 模擬 Context Manager 初始化資源
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 模擬資源清理與自動保存
        self._save()
        # Note: Sync exit cannot await flush(), user must call flush() manually or use async context manager

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
        # Buffered write
        self._buffer.append((text, metadata))
        if len(self._buffer) >= self.buffer_size:
            await self.flush()

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
        # Buffered write
        self._buffer.append((text, metadata))
        if len(self._buffer) >= self.buffer_size:
            await self.flush()

class ReMeHistoryMemory(BaseLongTermMemory):
    """
    RAG for Debate History using Qdrant.
    """
    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        # We don't use file storage for this one, but Base needs it.
        super().__init__(f"history_rag_{debate_id}")
        self.collection_name = f"debate_{debate_id}"
        
        # [Fix] Ensure collection exists immediately to avoid 404 on first search
        # We start with a small vector size default (768 is common for Ollama embeddings)
        # Note: Ideally we should use the actual embedding size from the model, but
        # ensure_collection is lazy/safe enough if we just trigger it.
        # However, we can't await in __init__. We'll just let the first flush handle creation,
        # but we need to handle the search 404 gracefully without scary logs,
        # or force a flush of an empty init message?
        # Better: Handle the search error gracefully in VectorStore, or here.
        # Actually, let's just make the buffer smaller for History to sync faster?
        # No, "why search failed" is the user question.
        # It failed because it doesn't exist.
        
    async def ensure_initialized(self):
        """Ensure the collection exists (async init)"""
        # We can't easily do this without a dummy embedding.
        # Let's just rely on VectorStore.search handling 404 silently or cleaner.
        pass

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
        # Buffered write
        self._buffer.append((text, metadata))
        if len(self._buffer) >= self.buffer_size:
            await self.flush()

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        logger.warning("ReMeHistoryMemory.retrieve is not implemented in sync mode. Use retrieve_async instead.")
        raise NotImplementedError("Use retrieve_async instead of the sync method.")

    async def retrieve_async(self, query: str, top_k: int = 3) -> List[Dict]:
        results = await VectorStore.search(self.collection_name, query, limit=top_k)
        return results