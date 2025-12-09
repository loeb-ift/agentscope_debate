
from typing import Dict, Any
import redis
import json
import hashlib
import time
from api.redis_client import get_redis_client
from jsonschema import validate, ValidationError

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._redis_client = get_redis_client()

    def _get_cache_key(self, tool_id: str, params: Dict[str, Any], exclude_params: list = None) -> str:
        """
        生成一個確定性的快取鍵。
        支援排除特定參數 (如 request_id, timestamp)。
        """
        cache_params = params.copy()
        
        # 1. 移除排除參數
        if exclude_params:
            for key in exclude_params:
                cache_params.pop(key, None)
        
        # 2. 移除常見的噪聲參數 (Global Filter)
        for key in ['_ts', 'timestamp', 'request_id', 'nonce']:
             cache_params.pop(key, None)

        param_string = json.dumps(cache_params, sort_keys=True)
        return f"cache:{tool_id}:{hashlib.md5(param_string.encode()).hexdigest()}"

    def register(self, tool: Any, version: str = "v1", group: str = "basic", lazy: bool = False):
        """
        註冊一個新的工具，並指定版本和工具組。
        支援 Lazy Loading: 如果 lazy=True，tool 應為一個返回工具實例的函數 (Factory)。
        """
        # 如果是 Lazy 模式，tool 是一個 factory function
        if lazy:
            if not callable(tool):
                raise ValueError("In lazy mode, tool must be a callable factory")
            
            # 我們需要知道工具名稱來生成 ID。
            # 這裡假設 factory function 有 .name 屬性，或者我們需要傳入 name
            # 為了簡單起見，我們先要求 instantiate 一次來獲取 metadata，或者要求傳入 name
            # 但這樣就不是完全 lazy 了。
            # 更好的方式是 lazy registration 需要顯式傳入 name。
            # 這裡我們先做一個簡單的 lazy：儲存 factory，首次調用時替換為 instance。
            # 但是 register 時需要 key (tool_id)。
            # 所以如果是 lazy，我們依然需要先知道 name。
            
            # 暫時策略：Lazy 註冊時必須提供 name (但目前的 API 簽名沒這個參數)
            # 為了不破壞現有代碼，我們先保持 register(instance) 兼容，
            # 並新增 register_lazy(name, factory, ...)
             
            pass # See register_lazy below
        
        # Eager Registration (Original logic)
        if not all(hasattr(tool, attr) for attr in ['name', 'describe', 'invoke']):
            raise ValueError("Tool must have name, describe, and invoke attributes")
        
        tool_id = f"{tool.name}:{version}"
        self._register_internal(tool_id, tool, version, group)

    def register_lazy(self, name: str, factory: callable, version: str = "v1", group: str = "basic", description: str = "Lazy loaded tool"):
        """
        Lazy 註冊工具。Factory 函數在第一次使用時被調用。
        """
        tool_id = f"{name}:{version}"
        self._tools[tool_id] = {
            "lazy": True,
            "factory": factory,
            "instance": None,
            "description": description, # Placeholder until loaded
            "version": version,
            "group": group,
            "schema": None # Will be loaded later
        }
        print(f"Tool '{tool_id}' registered lazily (group: {group}).")

    def _register_internal(self, tool_id: str, tool_instance: Any, version: str, group: str):
        self._tools[tool_id] = {
            "lazy": False,
            "instance": tool_instance,
            "description": tool_instance.describe(),
            "version": version,
            "group": group,
            "schema": getattr(tool_instance, 'schema', None),
            "auth_config": getattr(tool_instance, 'auth_config', None),
            "rate_limit_config": getattr(tool_instance, 'rate_limit_config', None),
            "cache_ttl": getattr(tool_instance, 'cache_ttl', None),
            "error_mapping": getattr(tool_instance, 'error_mapping', None)
        }
        print(f"Tool '{tool_id}' registered successfully (group: {group}).")

    def _ensure_loaded(self, tool_id: str):
        """如果工具是 Lazy 的且尚未加載，則加載它。"""
        if tool_id not in self._tools:
             return
        
        data = self._tools[tool_id]
        if data.get("lazy") and data.get("instance") is None:
            print(f"Lazy loading tool '{tool_id}'...")
            factory = data["factory"]
            instance = factory()
            # Re-register with actual instance data
            self._register_internal(tool_id, instance, data["version"], data["group"])

    def get_tool_data(self, tool_name: str, version: str = "v1") -> Dict[str, Any]:
        """
        根據名稱和版本獲取工具的完整中繼資料。
        """
        tool_id = f"{tool_name}:{version}"
        if tool_id not in self._tools:
            raise ValueError(f"Tool '{tool_id}' not found")
            
        self._ensure_loaded(tool_id)
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

    def _apply_tej_param_guard(self, tool_data: Dict[str, Any], params: Dict[str, Any]) -> tuple[Dict[str, Any], list]:
        """對 TEJ 工具套用參數護欄（觀測與預設）。"""
        warnings: list[str] = []
        group = tool_data.get("group") or ""
        provider = getattr(tool_data.get("instance"), "provider", "")
        is_tej = (group == "tej") or (str(provider).lower() == "tej")
        if not is_tej:
            return params, warnings
        # 建立副本，避免外部引用被修改
        p = dict(params) if params else {}
        if "coid" not in p:
            warnings.append("missing_param:coid")
        if "opts.limit" not in p:
            p["opts.limit"] = 50
            warnings.append("defaulted:opts.limit=50")
        # 日期區間觀測
        start = p.get("mdate.gte") or p.get("start_date")
        end = p.get("mdate.lte") or p.get("end_date")
        if not start or not end:
            warnings.append("suggest:add_date_range")
        else:
            from datetime import datetime
            try:
                d0 = datetime.strptime(str(start)[:10], "%Y-%m-%d")
                d1 = datetime.strptime(str(end)[:10], "%Y-%m-%d")
                if (d1 - d0).days > 366:
                    warnings.append("warn:date_span_too_large")
            except Exception:
                warnings.append("warn:date_parse_failed")
        return p, warnings

    def _normalize_tej_result(self, tool_data: Dict[str, Any], result: Dict[str, Any], warnings: list) -> Dict[str, Any]:
        """將 TEJ 結果標準化為 { data: [...] }，並附加 warnings。"""
        group = tool_data.get("group") or ""
        provider = getattr(tool_data.get("instance"), "provider", "")
        is_tej = (group == "tej") or (str(provider).lower() == "tej")
        if not is_tej or not isinstance(result, dict):
            # 非 TEJ 或非 dict，直接返回
            if warnings:
                if isinstance(result, dict):
                    result["warnings"] = warnings
            return result
        # 嘗試抽取資料陣列
        data = None
        if isinstance(result.get("data"), list):
            data = result.get("data")
            meta = result.get("meta")
        else:
            dt = result.get("datatable") if isinstance(result.get("datatable"), dict) else None
            data = dt.get("data") if isinstance(dt and dt.get("data"), list) else None
            meta = (dt.get("meta") if isinstance(dt, dict) else None)
        if isinstance(data, list):
            out = {"data": data}
            if meta is not None:
                out["meta"] = meta
            if warnings:
                out["warnings"] = warnings
            return out
        # 無法標準化，回傳原始並帶警示
        if warnings:
            result["warnings"] = warnings
        return result

    def invoke_tool(self, tool_name: str, params: Dict[str, Any], version: str = "v1") -> Dict[str, Any]:
        """
        調用工具，並處理參數驗證、快取和速率限制。
        """
        start_time = time.time()
        tool_id = f"{tool_name}:{version}"
        tool_data = self.get_tool_data(tool_name, version)
        tool = tool_data["instance"]
        schema = tool_data["schema"]
        
        # Cache Config
        cache_ttl = tool_data.get("cache_ttl")
        cache_exclude = getattr(tool, "cache_exclude_keys", []) # Tool specific exclusions

        rate_limit_config = tool_data.get("rate_limit_config")

        # 0. TEJ 參數護欄（先於驗證）
        params, tej_warnings = self._apply_tej_param_guard(tool_data, params)

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
        cache_key = None
        if cache_ttl and cache_ttl > 0:
            cache_key = self._get_cache_key(tool_id, params, exclude_params=cache_exclude)
            cached_result = self._redis_client.get(cache_key)
            if cached_result:
                result = json.loads(cached_result)
                result["used_cache"] = True
                result["_meta"] = {"exec_time": 0, "source": "cache"}
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
        except Exception as e:
             return {"error": f"Unexpected error: {str(e)}"}

        # 4.5 TEJ 回傳標準化
        result = self._normalize_tej_result(tool_data, result, tej_warnings)
        
        exec_time = time.time() - start_time
        
        # 5. 寫入快取 (Selective Caching)
        # 只有當結果沒有錯誤時才緩存，或者可以緩存錯誤但時間較短
        if cache_key and cache_ttl and cache_ttl > 0:
            is_error = isinstance(result, dict) and "error" in result
            if not is_error:
                self._redis_client.set(cache_key, json.dumps(result), ex=cache_ttl)
            else:
                # Optional: Cache errors for a shorter time (e.g., 60s) to prevent hammering
                # self._redis_client.set(cache_key, json.dumps(result), ex=60)
                pass
        
        if isinstance(result, dict):
            result["used_cache"] = False
            result["_meta"] = {
                "exec_time": round(exec_time, 4),
                "source": "live"
            }
            
        # Log slow tools
        if exec_time > 2.0:
            print(f"⚠️ Slow tool detected: {tool_id} took {exec_time:.2f}s")
            
        return result

    def list(self, groups: list[str] = None) -> Dict[str, Any]:
        """
        列出所有已註冊的工具及其詳細資訊。
        如果指定了 groups，則只返回屬於這些組的工具。
        注意：對於 Lazy 工具，如果尚未加載，可能只有基本描述。
        """
        result = {}
        for tool_id, data in self._tools.items():
            # tool_id format: name:version
            name = tool_id.split(":")[0]
            
            if groups is None or data.get("group", "basic") in groups:
                # If we want full details for list, we might need to load all.
                # But that defeats the purpose of lazy loading if we just want to list names.
                # For now, return what we have. If description/schema is critical,
                # we might need to partially load or store static metadata separately.
                # Here we assume lazy registration provided a basic description.
                
                # If schema is None (lazy), we might skip or show placeholder
                result[name] = {
                    "description": data["description"],
                    "version": data["version"],
                    "group": data.get("group", "basic"),
                    "schema": data.get("schema")
                }
        return result
    
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

