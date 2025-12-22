"""
動態工具加載器 - 從數據庫加載 OpenAPI 規範的工具
"""
from typing import Dict, Any, Optional
import os
import requests
from adapters.tool_adapter import ToolAdapter
from api.database import SessionLocal
from api import models


class OpenAPIToolAdapter(ToolAdapter):
    """基於 OpenAPI 規範的動態工具適配器"""
    
    def __init__(self, tool_config: Dict[str, Any]):
        self.tool_config = tool_config
        self._name = tool_config['name']
        self._version = tool_config.get('version', 'v1')
        self._description = tool_config.get('description', '')
        self.openapi_spec = tool_config.get('openapi_spec', {})
        self.base_url = tool_config.get('base_url', '')
        self.auth_type = tool_config.get('auth_type')
        self.auth_config = tool_config.get('auth_config', {})
        self.timeout = tool_config.get('timeout', 15)
        self.provider = tool_config.get('provider', 'custom')
        
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def version(self) -> str:
        return self._version
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def schema(self) -> Dict[str, Any]:
        """從 OpenAPI spec 提取參數 schema"""
        if not self.openapi_spec:
            return {}
        
        # 解析 OpenAPI spec 的第一個 path 的第一個 operation
        paths = self.openapi_spec.get('paths', {})
        for path, methods in paths.items():
            for method, operation in methods.items():
                parameters = operation.get('parameters', [])
                properties = {}
                required = []
                
                for param in parameters:
                    param_name = param['name']
                    param_schema = param.get('schema', {})
                    properties[param_name] = {
                        "type": param_schema.get('type', 'string'),
                        "description": param.get('description', '')
                    }
                    if param.get('required'):
                        required.append(param_name)
                
                return {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
        return {}
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }
    
    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """執行 API 調用，含參數別名適配、觀測/警示、TEJ 預設參數與回傳標準化"""
        if not self.openapi_spec:
            return {"error": "No OpenAPI spec defined"}
        
        # 0. 參數別名適配 (Parameter Alias Adaptation)
        # 根據 provider 與需求將常見別名轉換為標準參數名
        params = kwargs.copy()
        warnings: list[str] = []
        
        # 定義全域常見別名映射
        ALIAS_MAP = {
            "symbol": ["ticker", "stock_id", "coid"],
            "ticker": ["symbol", "stock_id", "coid"],
            "coid": ["symbol", "ticker", "stock_id", "id"],
            "company_id": ["coid", "ticker", "symbol", "id"]
        }
        
        # 取得當前工具需要的參數列表 (從 schema)
        tool_schema = self.schema
        expected_params = list(tool_schema.get("properties", {}).keys())
        
        for target, aliases in ALIAS_MAP.items():
            # 如果工具需要 target，但 params 中沒有 target 卻有 alias
            if target in expected_params and target not in params:
                for alias in aliases:
                    if alias in params:
                        params[target] = params[alias]
                        warnings.append(f"parameter_adapted: {alias} -> {target}")
                        break

        # 1. 構建 URL
        paths = self.openapi_spec.get('paths', {})
        if not paths:
            return {"error": "No paths defined in OpenAPI spec"}
        
        path = list(paths.keys())[0]
        url = f"{self.base_url}{path}"
        
        # 2. 準備參數 (已在步驟 0 完成初步適配)
        # 3. 添加認證
        if self.auth_type == "api_key":
            param_name = self.auth_config.get('param', 'api_key')
            param_in = self.auth_config.get('in', 'query')
            
            # 從環境變量獲取 API Key
            env_key = f"{self.provider.upper()}_API_KEY"
            api_key = os.getenv(env_key)
            
            if not api_key:
                return {"error": f"Missing {env_key} environment variable"}
            
            if param_in == "query":
                params[param_name] = api_key
            elif param_in == "header":
                # TODO: 支持 header 認證
                pass
        
        # 3.5 TEJ 工具的觀測與預設參數（護欄）
        try:
            if self.provider and self.provider.lower() == 'tej':
                # 觀測：缺少 coid 警示（大多數 TEJ 工具需要）
                if 'coid' not in params:
                    warnings.append("missing_param:coid")
                # 預設 opts.limit（避免空切片），若未提供
                if 'opts.limit' not in params:
                    params['opts.limit'] = 50
                    warnings.append("defaulted:opts.limit=50")
                # 日期區間觀測（不強制轉換，只提示）
                # 支援兩種常見鍵：mdate.gte/lte 或 start_date/end_date
                start = params.get('mdate.gte') or params.get('start_date')
                end = params.get('mdate.lte') or params.get('end_date')
                if not start or not end:
                    warnings.append("suggest:add_date_range")
                else:
                    # 粗略檢查跨度是否過大（> 366 天）
                    from datetime import datetime
                    fmt = "%Y-%m-%d"
                    try:
                        d0 = datetime.strptime(str(start)[:10], fmt)
                        d1 = datetime.strptime(str(end)[:10], fmt)
                        if (d1 - d0).days > 366:
                            warnings.append("warn:date_span_too_large")
                    except Exception:
                        warnings.append("warn:date_parse_failed")
        except Exception:
            # 不阻斷流程
            pass
        
        # 4. 執行請求
        try:
            print(f"DEBUG: OpenAPIToolAdapter calling {url} with params: {params}")
            
            # 添加 User-Agent 避免被 WAF 攔截 (參考 tej_adapter.py)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            raw = response.json()
            
            # 5. 回傳標準化：若為 TEJ，統一輸出 { data: [...] }
            if self.provider and self.provider.lower() == 'tej':
                data = None
                if isinstance(raw.get('data'), list):
                    data = raw.get('data')
                else:
                    data = raw.get('datatable', {}).get('data') if isinstance(raw.get('datatable'), dict) else None
                if isinstance(data, list):
                    out = {"data": data}
                    # 若有 meta，附帶
                    meta = raw.get('meta') or (raw.get('datatable', {}).get('meta') if isinstance(raw.get('datatable'), dict) else None)
                    if meta is not None:
                        out['meta'] = meta
                    if warnings:
                        out['warnings'] = warnings
                    return out
                else:
                    # 無法標準化，仍回傳原始，但帶上警示
                    if warnings:
                        raw['warnings'] = warnings
                    return raw
            
            # 非 TEJ：原樣返回，但附上可能的警示
            if warnings and isinstance(raw, dict):
                raw['warnings'] = warnings
            return raw
        except requests.exceptions.Timeout:
            return {"error": f"Request timeout after {self.timeout}s", "warnings": warnings} if warnings else {"error": f"Request timeout after {self.timeout}s"}
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}", "warnings": warnings} if warnings else {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}", "warnings": warnings} if warnings else {"error": f"Request failed: {str(e)}"}


class DynamicToolLoader:
    """從數據庫動態加載工具到 tool_registry"""
    
    @staticmethod
    def load_all_tools(tool_registry):
        """加載所有啟用的 OpenAPI 工具"""
        db = SessionLocal()
        try:
            # 只加載啟用的 API 類型工具，且有 openapi_spec 的
            tools = db.query(models.Tool).filter(
                models.Tool.enabled == True,
                models.Tool.type == "api",
                models.Tool.openapi_spec.isnot(None)
            ).all()
            
            loaded_count = 0
            for tool in tools:
                try:
                    adapter = OpenAPIToolAdapter({
                        'name': tool.name,
                        'version': tool.version or 'v1',
                        'description': tool.description or '',
                        'openapi_spec': tool.openapi_spec,
                        'base_url': tool.base_url,
                        'auth_type': tool.auth_type,
                        'auth_config': tool.auth_config or {},
                        'provider': tool.provider or 'custom',
                        'timeout': tool.timeout or 15
                    })
                    
                    group = tool.provider or tool.group or "custom"
                    tool_registry.register(adapter, group=group)
                    print(f"✅ Loaded OpenAPI tool: {tool.name} (provider: {group})")
                    loaded_count += 1
                except Exception as e:
                    print(f"❌ Failed to load tool {tool.name}: {e}")
            
            print(f"📦 Total OpenAPI tools loaded: {loaded_count}")
            return loaded_count
        finally:
            db.close()
    
    @staticmethod
    def reload_tool(tool_registry, tool_name: str):
        """重新加載單個工具（用於更新後刷新）"""
        db = SessionLocal()
        try:
            tool = db.query(models.Tool).filter(
                models.Tool.name == tool_name,
                models.Tool.enabled == True,
                models.Tool.type == "api",
                models.Tool.openapi_spec.isnot(None)
            ).first()
            
            if not tool:
                print(f"⚠️  Tool {tool_name} not found or not enabled")
                return False
            
            adapter = OpenAPIToolAdapter({
                'name': tool.name,
                'version': tool.version or 'v1',
                'description': tool.description or '',
                'openapi_spec': tool.openapi_spec,
                'base_url': tool.base_url,
                'auth_type': tool.auth_type,
                'auth_config': tool.auth_config or {},
                'provider': tool.provider or 'custom',
                'timeout': tool.timeout or 15
            })
            
            group = tool.provider or tool.group or "custom"
            tool_registry.register(adapter, group=group)
            print(f"🔄 Reloaded tool: {tool.name}")
            return True
        except Exception as e:
            print(f"❌ Failed to reload tool {tool_name}: {e}")
            return False
        finally:
            db.close()
