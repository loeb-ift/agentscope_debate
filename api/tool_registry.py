
from typing import Dict, Any
import redis
import json
import hashlib
from jsonschema import validate, ValidationError

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

    def _get_cache_key(self, tool_id: str, params: Dict[str, Any]) -> str:
        """
        生成一個確定性的快取鍵。
        """
        param_string = json.dumps(params, sort_keys=True)
        return f"cache:{tool_id}:{hashlib.md5(param_string.encode()).hexdigest()}"

    def register(self, tool: Any, version: str = "v1"):
        """
        註冊一個新的工具，並指定版本。
        """
        if not all(hasattr(tool, attr) for attr in ['name', 'describe', 'invoke']):
            raise ValueError("Tool must have name, describe, and invoke attributes")
        
        tool_id = f"{tool.name}:{version}"
        if tool_id in self._tools:
            print(f"Warning: Tool '{tool_id}' is already registered. Overwriting.")

        self._tools[tool_id] = {
            "instance": tool,
            "description": tool.describe(),
            "version": version,
            "schema": getattr(tool, 'schema', None),
            "auth_config": getattr(tool, 'auth_config', None),
            "rate_limit_config": getattr(tool, 'rate_limit_config', None),
            "cache_ttl": getattr(tool, 'cache_ttl', None), # in seconds
            "error_mapping": getattr(tool, 'error_mapping', None)
        }
        print(f"Tool '{tool_id}' registered successfully.")

    def get_tool_data(self, tool_name: str, version: str = "v1") -> Dict[str, Any]:
        """
        根據名稱和版本獲取工具的完整中繼資料。
        """
        tool_id = f"{tool_name}:{version}"
        if tool_id not in self._tools:
            raise ValueError(f"Tool '{tool_id}' not found")
        return self._tools[tool_id]

    def get_tools(self):
        """
        獲取所有已註冊的工具。
        """
        return self._tools.values()

    def _check_rate_limit(self, tool_id: str, rate_limit_config: Dict[str, Any]) -> bool:
        """
        檢查工具的速率限制。
        """
        if not rate_limit_config:
            return True

        limit = rate_limit_config.get("limit")
        period = rate_limit_config.get("period")

        if not limit or not period:
            return True

        key = f"rate_limit:{tool_id}"
        count = self._redis_client.get(key)

        if count and int(count) >= limit:
            return False

        pipe = self._redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, period)
        pipe.execute()

        return True

    def invoke_tool(self, tool_name: str, params: Dict[str, Any], version: str = "v1") -> Dict[str, Any]:
        """
        調用工具，並處理參數驗證、快取和速率限制。
        """
        tool_id = f"{tool_name}:{version}"
        tool_data = self.get_tool_data(tool_name, version)
        tool = tool_data["instance"]
        schema = tool_data["schema"]
        cache_ttl = tool_data.get("cache_ttl")
        rate_limit_config = tool_data.get("rate_limit_config")

        # 1. 速率限制
        if not self._check_rate_limit(tool_id, rate_limit_config):
            return {"error": "Rate limit exceeded"}

        # 2. 參數驗證
        if schema:
            try:
                validate(instance=params, schema=schema)
            except ValidationError as e:
                return {"error": f"Parameter validation failed: {e.message}"}

        # 3. 檢查快取
        if cache_ttl and cache_ttl > 0:
            cache_key = self._get_cache_key(tool_id, params)
            cached_result = self._redis_client.get(cache_key)
            if cached_result:
                result = json.loads(cached_result)
                result["used_cache"] = True
                return result

        # 4. 執行工具
        try:
            result = tool.invoke(**params)
            if hasattr(result, "to_dict"):
                result = result.to_dict()
        except RuntimeError as e:
            error_mapping = tool_data.get("error_mapping")
            if error_mapping:
                error_message = error_mapping.get(type(e).__name__)
                if error_message:
                    return {"error": error_message}
            return {"error": str(e)}

        # 5. 寫入快取
        if cache_ttl and cache_ttl > 0:
            cache_key = self._get_cache_key(tool_id, params)
            self._redis_client.set(cache_key, json.dumps(result), ex=cache_ttl)
        
        result["used_cache"] = False
        return result

    def list(self) -> Dict[str, Any]:
        """
        列出所有已註冊的工具及其詳細資訊。
        """
        return {
            name: {
                "description": data["description"],
                "version": data["version"],
                "schema": data["schema"]
            } for name, data in self._tools.items()
        }
    
    def list_tools(self) -> Dict[str, Any]:
        """
        列出所有已註冊的工具（返回 tool_id: tool_data 格式）。
        """
        return self._tools
    
    def get_tool_info(self, tool_name: str, version: str = "v1") -> Dict[str, Any]:
        """
        獲取單個工具的資訊（用於工具集管理）。
        
        返回格式：
        {
            "name": "tej.stock_price",
            "version": "v1",
            "description": "...",
            "schema": {...}
        }
        """
        tool_id = f"{tool_name}:{version}"
        
        if tool_id not in self._tools:
            return None
        
        tool_data = self._tools[tool_id]
        return {
            "name": tool_name,
            "version": version,
            "description": tool_data["description"],
            "schema": tool_data["schema"]
        }

tool_registry = ToolRegistry()

