# TEJ 工具 OpenAPI 規範管理實現方案

## 📋 目標
將現有的 TEJ 工具（硬編碼在 `tej_adapter.py`）遷移到基於 OpenAPI 規範的數據庫管理模式，實現前端可視化管理。

---

## 🏗️ 架構設計

### 1. 數據模型擴展

#### 1.1 擴展 `Tool` 模型
```python
# api/models.py

class Tool(Base):
    __tablename__ = "tools"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)  # e.g., "tej.company_info"
    version = Column(String, default="v1")
    description = Column(Text)
    
    # 新增字段
    tool_type = Column(String, default="api")  # "api", "python", "internal"
    provider = Column(String, nullable=True)  # "tej", "yfinance", "custom"
    
    # OpenAPI 規範（JSON）
    openapi_spec = Column(JSON, nullable=True)  # 完整的 OpenAPI 3.0 spec
    
    # 認證配置
    auth_type = Column(String, nullable=True)  # "api_key", "oauth2", "basic", "none"
    auth_config = Column(JSON, nullable=True)  # {"in": "query", "param": "api_key"}
    
    # 速率限制
    rate_limit = Column(JSON, nullable=True)  # {"tps": 5, "burst": 10}
    
    # 緩存配置
    cache_ttl = Column(Integer, default=3600)  # seconds
    
    # 其他配置
    base_url = Column(String, nullable=True)
    timeout = Column(Integer, default=15)
    
    # 元數據
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 1.2 OpenAPI Spec 結構示例（TEJ Company Info）
```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "TEJ Company Info",
    "version": "1.0.0",
    "description": "查詢台灣上市櫃公司基本資料"
  },
  "servers": [
    {
      "url": "https://api.tej.com.tw/api/datatables"
    }
  ],
  "paths": {
    "/TRAIL/TAIACC.json": {
      "get": {
        "summary": "取得公司基本資料",
        "operationId": "getCompanyInfo",
        "parameters": [
          {
            "name": "coid",
            "in": "query",
            "description": "公司代碼（如 2330）",
            "required": true,
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "opts.limit",
            "in": "query",
            "schema": {
              "type": "integer",
              "default": 50
            }
          }
        ],
        "responses": {
          "200": {
            "description": "成功",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "data": {
                      "type": "array"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "ApiKeyAuth": {
        "type": "apiKey",
        "in": "query",
        "name": "api_key"
      }
    }
  },
  "security": [
    {
      "ApiKeyAuth": []
    }
  ]
}
```

---

## 🔄 實現步驟

### Phase 1: 數據庫遷移與模型更新

1. **創建數據庫遷移腳本**
   ```bash
   # 添加新字段到 tools 表
   ALTER TABLE tools ADD COLUMN tool_type VARCHAR DEFAULT 'api';
   ALTER TABLE tools ADD COLUMN provider VARCHAR;
   ALTER TABLE tools ADD COLUMN openapi_spec JSON;
   ALTER TABLE tools ADD COLUMN auth_type VARCHAR;
   ALTER TABLE tools ADD COLUMN auth_config JSON;
   ALTER TABLE tools ADD COLUMN rate_limit JSON;
   ALTER TABLE tools ADD COLUMN cache_ttl INTEGER DEFAULT 3600;
   ALTER TABLE tools ADD COLUMN base_url VARCHAR;
   ALTER TABLE tools ADD COLUMN timeout INTEGER DEFAULT 15;
   ```

2. **更新 Pydantic Schemas**
   ```python
   # api/schemas.py
   
   class ToolCreate(BaseModel):
       name: str
       version: str = "v1"
       description: str
       tool_type: str = "api"  # "api", "python", "internal"
       provider: Optional[str] = None
       openapi_spec: Optional[Dict[str, Any]] = None
       auth_type: Optional[str] = None
       auth_config: Optional[Dict[str, Any]] = None
       rate_limit: Optional[Dict[str, Any]] = None
       cache_ttl: int = 3600
       base_url: Optional[str] = None
       timeout: int = 15
   ```

### Phase 2: 動態工具加載器

創建 `DynamicToolLoader` 來從數據庫加載並註冊工具：

```python
# worker/dynamic_tool_loader.py

from typing import Dict, Any
import requests
from api.database import SessionLocal
from api import models
from adapters.tool_adapter import ToolAdapter

class OpenAPIToolAdapter(ToolAdapter):
    """動態 OpenAPI 工具適配器"""
    
    def __init__(self, tool_config: Dict[str, Any]):
        self.tool_config = tool_config
        self._name = tool_config['name']
        self._version = tool_config['version']
        self._description = tool_config['description']
        self.openapi_spec = tool_config['openapi_spec']
        self.base_url = tool_config.get('base_url')
        self.auth_type = tool_config.get('auth_type')
        self.auth_config = tool_config.get('auth_config', {})
        self.timeout = tool_config.get('timeout', 15)
        
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
        """執行 API 調用"""
        # 1. 構建 URL
        paths = self.openapi_spec.get('paths', {})
        path = list(paths.keys())[0]
        url = f"{self.base_url}{path}"
        
        # 2. 添加認證
        params = kwargs.copy()
        if self.auth_type == "api_key":
            param_name = self.auth_config.get('param', 'api_key')
            api_key = os.getenv(f"{self.tool_config['provider'].upper()}_API_KEY")
            params[param_name] = api_key
        
        # 3. 執行請求
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


class DynamicToolLoader:
    """從數據庫動態加載工具"""
    
    @staticmethod
    def load_all_tools(tool_registry):
        """加載所有啟用的工具到 registry"""
        db = SessionLocal()
        try:
            tools = db.query(models.Tool).filter(
                models.Tool.is_active == True,
                models.Tool.tool_type == "api"
            ).all()
            
            for tool in tools:
                adapter = OpenAPIToolAdapter({
                    'name': tool.name,
                    'version': tool.version,
                    'description': tool.description,
                    'openapi_spec': tool.openapi_spec,
                    'base_url': tool.base_url,
                    'auth_type': tool.auth_type,
                    'auth_config': tool.auth_config,
                    'provider': tool.provider,
                    'timeout': tool.timeout
                })
                
                group = tool.provider or "custom"
                tool_registry.register(adapter, group=group)
                print(f"✅ Loaded tool: {tool.name} (provider: {group})")
        finally:
            db.close()
```

### Phase 3: 初始化數據遷移

創建腳本將現有 TEJ 工具轉換為 OpenAPI 規範：

```python
# scripts/migrate_tej_tools_to_openapi.py

from api.database import SessionLocal
from api import models
import json

def migrate_tej_tools():
    db = SessionLocal()
    
    # TEJ Company Info 示例
    tej_company_info = models.Tool(
        name="tej.company_info",
        version="v1",
        description="查詢台灣上市櫃公司基本資料",
        tool_type="api",
        provider="tej",
        base_url="https://api.tej.com.tw/api/datatables",
        auth_type="api_key",
        auth_config={"in": "query", "param": "api_key"},
        rate_limit={"tps": 5, "burst": 10},
        cache_ttl=21600,  # 6 hours
        timeout=15,
        openapi_spec={
            "openapi": "3.0.0",
            "info": {
                "title": "TEJ Company Info",
                "version": "1.0.0"
            },
            "paths": {
                "/TRAIL/TAIACC.json": {
                    "get": {
                        "parameters": [
                            {
                                "name": "coid",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "公司代碼"
                            }
                        ]
                    }
                }
            }
        }
    )
    
    db.add(tej_company_info)
    db.commit()
    print("✅ TEJ tools migrated to OpenAPI format")

if __name__ == "__main__":
    migrate_tej_tools()
```

### Phase 4: 前端管理界面

在 `web/app.py` 中添加 TEJ 工具管理 Tab：

```python
# web/app.py - 新增 Tab

with gr.Tab("🔧 TEJ 工具管理"):
    gr.Markdown("### 管理 TEJ API 工具配置")
    
    with gr.Row():
        with gr.Column(scale=2):
            tej_tools_table = gr.Dataframe(
                headers=["ID", "名稱", "描述", "Provider", "狀態"],
                label="TEJ 工具列表"
            )
            refresh_tej_btn = gr.Button("🔄 刷新")
        
        with gr.Column(scale=3):
            gr.Markdown("### 編輯 OpenAPI 規範")
            tool_id_input = gr.Textbox(label="Tool ID", interactive=False)
            tool_name_input = gr.Textbox(label="工具名稱")
            tool_desc_input = gr.Textbox(label="描述")
            openapi_editor = gr.Code(
                label="OpenAPI Spec (JSON)",
                language="json",
                lines=20
            )
            save_tej_tool_btn = gr.Button("💾 保存", variant="primary")
            tej_msg = gr.Textbox(label="操作結果")
    
    # 事件綁定
    refresh_tej_btn.click(list_tej_tools, outputs=tej_tools_table)
    tej_tools_table.select(load_tej_tool_detail, outputs=[tool_id_input, tool_name_input, tool_desc_input, openapi_editor])
    save_tej_tool_btn.click(update_tej_tool, inputs=[tool_id_input, tool_name_input, tool_desc_input, openapi_editor], outputs=tej_msg)
```

---

## 🎯 優勢

1. **統一管理**：所有工具（TEJ、自定義）使用相同的管理界面
2. **標準化**：基於 OpenAPI 3.0 標準，易於擴展
3. **可視化**：前端可直接編輯工具配置，無需修改代碼
4. **動態加載**：新增工具無需重啟服務
5. **版本控制**：每個工具可以有多個版本
6. **權限管理**：可以為不同 Agent 分配不同的工具集

---

## 📝 實現優先級

1. ✅ **Phase 1**: 數據庫模型擴展（1-2 小時）
2. ✅ **Phase 2**: 動態工具加載器（2-3 小時）
3. ✅ **Phase 3**: 遷移現有 TEJ 工具（1 小時）
4. ✅ **Phase 4**: 前端管理界面（2-3 小時）

**總計**: 約 1 個工作日

---

## 🚀 下一步

是否開始實現？建議從 Phase 1 開始，逐步推進。
