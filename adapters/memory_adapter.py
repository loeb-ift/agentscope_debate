from typing import Dict, Any
from adapters.tool_adapter import ToolAdapter
from worker.memory import HippocampalMemory

class SearchSharedMemory(ToolAdapter):
    name = "search_shared_memory"
    version = "v1"
    description = "從共享海馬體記憶中檢索過往的工具調用結果與知識。支援語義搜尋與來源過濾。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string", 
                    "description": "搜尋關鍵字或問題 (e.g., '台積電上季營收', '半導體產業趨勢')"
                },
                "filter_tool": {
                    "type": "string",
                    "description": "過濾特定工具來源 (e.g., 'tej.stock_price', 'searxng.search')"
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "返回結果數量限制"
                }
            },
            "required": ["query"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        # Note: This tool needs to access the debate context.
        # Ideally, tools are stateless, but HippocampalMemory requires debate_id.
        # We assume the debate_id is available in the environment or passed implicitly.
        # For this implementation, we might need to rely on a global context or pass debate_id explicitly if possible.
        # However, HippocampalMemory in worker/memory.py uses a debate_id to initialize.
        
        # In a real microservice, the tool execution context would carry the debate_id.
        # Here, we might need a workaround or assume a specific debate_id if running in a single worker context.
        
        # WORKAROUND: For now, we instantiate HippocampalMemory with a placeholder or retrieve from current task context if available.
        # Since we are inside the worker process, we might not have easy access to the specific debate instance here without dependency injection.
        
        # To strictly follow the architecture, tools should be independent. 
        # But this is an "Introspective Tool".
        
        # Let's try to infer debate_id or use a wildcard search if possible.
        # Or, we update the ToolAdapter interface to accept context.
        
        # For simplicity in this optimization phase, we will assume we can search the "global" or "latest" debate, 
        # OR we rely on the caller to inject the memory instance.
        
        # Actually, HippocampalMemory uses `hippocampus_{debate_id}` collection.
        # If we want to search *across* debates (Long-term Wisdom), we might search a global collection.
        # If we want to search *within* the current debate, we need the ID.
        
        # Let's assume we search a global "Knowledge Base" for now, or allow the user to pass debate_id if known.
        
        import asyncio
        from worker.memory import HippocampalMemory
        
        debate_id = kwargs.get("_context_debate_id", "global") # Hypothetical context injection
        query = kwargs.get("query")
        limit = kwargs.get("limit", 5)
        filter_tool = kwargs.get("filter_tool")
        
        # We need to run async code in sync invoke
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # We expect the caller (DebateCycle) to inject the 'debate_id' into kwargs.
        # This ensures memory is scoped to the current debate only.
        
        debate_id = kwargs.get("debate_id")
        if not debate_id:
            return {"error": "Internal Error: 'debate_id' context is missing. Cannot access shared memory."}
        
        mem = HippocampalMemory(debate_id=debate_id)
        
        try:
            result = loop.run_until_complete(mem.search_shared_memory(query, limit, filter_tool))
            return {"result": result}
        finally:
            loop.close()
