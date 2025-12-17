from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import yaml
import os
from worker.tool_manager import tool_manager, ToolDefinition
from api.redis_client import get_redis_client
import json

router = APIRouter(prefix="/cache", tags=["cache"])

class InvalidateRequest(BaseModel):
    tool_name: str

class ToolConfigUpdate(BaseModel):
    tool_name: str
    lifecycle: str
    ttl: int = None

@router.get("/config")
async def get_tool_config():
    """Get current tool registry configuration"""
    config_path = os.path.join(os.path.dirname(__file__), "../../config/tool_registry.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")

@router.post("/invalidate")
async def invalidate_tool_cache(request: InvalidateRequest):
    """Manually invalidate cache for a specific tool (by bumping version salt in memory?)"""
    # Note: Changing salt requires code change or persistent salt storage.
    # For now, we can just delete keys matching the pattern in Redis.
    
    redis = get_redis_client()
    tool_name = request.tool_name
    
    # We don't know the exact version salt used by worker easily without querying worker state.
    # But we know the prefix "memory:working:*"
    # This is an expensive operation (SCAN).
    
    # Alternative: Just delete the tool definition from memory? No.
    
    # Better approach: We can't easily delete specific tool keys because the key is hashed params.
    # But we CAN trigger a "Reload" of the tool manager which might update the salt if we store salt in YAML.
    # But currently salt is hardcoded in code 'v5'.
    
    return {"status": "not_implemented_fully", "message": "Manual invalidation requires Redis SCAN. Use with caution."}

@router.get("/stats")
async def get_cache_stats():
    """Get cache statistics (mock or real)"""
    redis = get_redis_client()
    info = redis.info("memory")
    dbsize = redis.dbsize()
    
    return {
        "redis_memory_used": info.get("used_memory_human"),
        "total_keys": dbsize,
        "tool_policies": len(tool_manager.tool_map)
    }

@router.post("/reload")
async def reload_config():
    """Reload Tool Registry from YAML"""
    try:
        tool_manager._load_registry()
        return {"status": "success", "message": "Tool Registry reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))