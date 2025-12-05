# 工具集系統實現指南

## 完成時間：2025-12-05 17:10

---

## ✅ 任務 1：ToolSet API 端點（已完成）

### 實現的端點

#### ToolSet CRUD
- ✅ `POST /api/v1/toolsets` - 創建工具集
- ✅ `GET /api/v1/toolsets` - 列出所有工具集（支持 is_global 篩選）
- ✅ `GET /api/v1/toolsets/{toolset_id}` - 獲取工具集詳情
- ✅ `PUT /api/v1/toolsets/{toolset_id}` - 更新工具集
- ✅ `DELETE /api/v1/toolsets/{toolset_id}` - 刪除工具集

#### Agent-ToolSet 關聯
- ✅ `POST /api/v1/agents/{agent_id}/toolsets` - 分配工具集給 Agent
- ✅ `GET /api/v1/agents/{agent_id}/toolsets` - 獲取 Agent 的工具集
- ✅ `GET /api/v1/agents/{agent_id}/available-tools` - 獲取 Agent 可用工具
- ✅ `DELETE /api/v1/agents/{agent_id}/toolsets/{toolset_id}` - 移除分配

#### 初始化
- ✅ `POST /api/v1/toolsets/initialize-global` - 初始化全局工具集

### 測試 API

```bash
# 1. 初始化全局工具集
curl -X POST "http://localhost:8000/api/v1/toolsets/initialize-global"

# 2. 創建台股分析工具集
curl -X POST "http://localhost:8000/api/v1/toolsets" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "台股分析工具集",
    "description": "專門用於台灣股市分析",
    "tool_names": [
      "tej.stock_price",
      "tej.company_info",
      "tej.monthly_revenue",
      "tej.financial_summary"
    ],
    "is_global": false
  }'

# 3. 列出所有工具集
curl "http://localhost:8000/api/v1/toolsets"

# 4. 分配工具集給 Agent
curl -X POST "http://localhost:8000/api/v1/agents/{agent_id}/toolsets" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "{agent_id}",
    "toolset_id": "{toolset_id}"
  }'

# 5. 獲取 Agent 可用工具
curl "http://localhost:8000/api/v1/agents/{agent_id}/available-tools"
```

---

## 🔄 任務 2：更新 debate_cycle.py（實現指南）

### 目標
移除硬編碼的工具列表，改用動態獲取 Agent 的可用工具。

### 修改位置
`worker/debate_cycle.py` 的 `_agent_turn` 方法

### 修改前（硬編碼）
```python
user_prompt = f"""
**可用工具列表**：
1. **TEJ 台股工具**：
   - tej.stock_price: 查詢台股股價
   - tej.company_info: 查詢公司資料
   ...
"""
```

### 修改後（動態獲取）
```python
from api.database import SessionLocal
from api.toolset_service import ToolSetService

def _agent_turn(self, agent: AgentBase, side: str, round_num: int) -> str:
    # 1. 獲取 Agent 可用的工具
    db = SessionLocal()
    try:
        # 假設 agent 有 id 屬性
        agent_id = getattr(agent, 'id', None)
        
        if agent_id:
            available_tools = ToolSetService.get_agent_available_tools(db, agent_id)
            tools_prompt = ToolSetService.format_tools_for_prompt(available_tools)
        else:
            # 如果沒有 agent_id，使用全局工具集
            global_toolset = db.query(models.ToolSet).filter(
                models.ToolSet.is_global == True
            ).first()
            
            if global_toolset:
                available_tools = []
                for tool_name in global_toolset.tool_names:
                    tool_info = tool_registry.get_tool_info(tool_name)
                    if tool_info:
                        available_tools.append(tool_info)
                tools_prompt = ToolSetService.format_tools_for_prompt(available_tools)
            else:
                tools_prompt = "**可用工具**：無"
    finally:
        db.close()
    
    # 2. 構建 Prompt
    user_prompt = f"""
這是第 {round_num} 輪辯論。

{tools_prompt}

請根據需要選擇合適的工具來完成任務。
只輸出 JSON 格式的工具調用，不要其他文字。
"""
```

### 完整修改代碼

```python
# worker/debate_cycle.py

from api.database import SessionLocal
from api import models
from api.toolset_service import ToolSetService
from api.tool_registry import tool_registry

class DebateCycle:
    # ... 其他代碼 ...
    
    def _agent_turn(self, agent: AgentBase, side: str, round_num: int) -> str:
        """
        執行單個 Agent 的回合：思考 -> 工具 -> 發言
        """
        print(f"Agent {agent.name} ({side}) is thinking...")
        
        # 獲取 Agent 可用的工具
        db = SessionLocal()
        try:
            agent_id = getattr(agent, 'id', None)
            
            if agent_id:
                available_tools = ToolSetService.get_agent_available_tools(db, agent_id)
            else:
                # 使用全局工具集
                global_toolset = db.query(models.ToolSet).filter(
                    models.ToolSet.is_global == True
                ).first()
                
                available_tools = []
                if global_toolset:
                    for tool_name in global_toolset.tool_names:
                        tool_info = tool_registry.get_tool_info(tool_name)
                        if tool_info:
                            available_tools.append(tool_info)
            
            tools_prompt = ToolSetService.format_tools_for_prompt(available_tools)
        finally:
            db.close()
        
        # 構建 Prompt
        system_prompt = f"""你是 {agent.name}，代表{side}。
辯題：{self.topic}

**重要指示**：
1. 你可以使用工具獲取真實數據
2. 工具調用格式必須是純 JSON
3. 調用工具後，你會收到數據，然後基於數據發言
"""
        
        user_prompt = f"""
這是第 {round_num} 輪辯論。主席戰略摘要：{self.analysis_result.get('step5_summary', '無')}

{tools_prompt}

**請選擇合適的工具**（只輸出 JSON，不要其他文字）：
"""
        
        response = call_llm(user_prompt, system_prompt=system_prompt)
        print(f"DEBUG: Agent {agent.name} raw response: {response[:500]}")
        
        # ... 其餘的工具調用解析邏輯保持不變 ...
```

### 需要的修改

1. **添加 import**
   ```python
   from api.database import SessionLocal
   from api import models
   from api.toolset_service import ToolSetService
   from api.tool_registry import tool_registry
   ```

2. **修改 Agent 創建邏輯**（在 `worker/tasks.py`）
   - 為 Agent 添加 `id` 屬性
   - 或者使用 Agent 名稱映射到資料庫

3. **測試**
   - 創建 Agent 並分配工具集
   - 啟動辯論
   - 驗證 Agent 只使用分配的工具

---

## 🎨 任務 3：Gradio 前端（實現指南）

### 3.1 工具集管理介面

創建 `web/toolset_management.py`：

```python
import gradio as gr
import requests
import json

API_BASE = "http://api:8000"

def create_toolset_ui():
    """創建工具集管理 UI"""
    
    with gr.TabItem("工具集管理"):
        gr.Markdown("## 工具集管理")
        
        with gr.Row():
            # 左側：創建工具集
            with gr.Column(scale=1):
                gr.Markdown("### 創建新工具集")
                
                toolset_name = gr.Textbox(label="工具集名稱")
                toolset_desc = gr.Textbox(label="描述", lines=2)
                
                # 獲取所有可用工具
                all_tools = get_all_tools()
                tool_choices = [f"{t['name']} - {t['description'][:50]}" for t in all_tools]
                
                selected_tools = gr.CheckboxGroup(
                    choices=tool_choices,
                    label="選擇工具"
                )
                
                is_global = gr.Checkbox(label="設為全局工具集", value=False)
                
                create_btn = gr.Button("創建工具集", variant="primary")
                create_output = gr.Textbox(label="結果")
            
            # 右側：工具集列表
            with gr.Column(scale=2):
                gr.Markdown("### 現有工具集")
                
                refresh_btn = gr.Button("刷新列表")
                toolsets_table = gr.DataFrame(
                    headers=["ID", "名稱", "描述", "工具數量", "類型"],
                    label="工具集列表"
                )
                
                with gr.Row():
                    toolset_selector = gr.Dropdown(label="選擇工具集")
                    view_btn = gr.Button("查看詳情")
                    delete_btn = gr.Button("刪除", variant="stop")
                
                toolset_details = gr.JSON(label="工具集詳情")
        
        # 事件處理
        create_btn.click(
            fn=create_toolset,
            inputs=[toolset_name, toolset_desc, selected_tools, is_global],
            outputs=create_output
        )
        
        refresh_btn.click(
            fn=list_toolsets,
            outputs=toolsets_table
        )
        
        view_btn.click(
            fn=get_toolset_details,
            inputs=toolset_selector,
            outputs=toolset_details
        )

def get_all_tools():
    """獲取所有可用工具"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/tools")
        return response.json()
    except:
        return []

def create_toolset(name, description, selected_tools, is_global):
    """創建工具集"""
    # 解析選中的工具名稱
    tool_names = [t.split(" - ")[0] for t in selected_tools]
    
    data = {
        "name": name,
        "description": description,
        "tool_names": tool_names,
        "is_global": is_global
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/toolsets",
            json=data
        )
        if response.status_code == 201:
            return f"✓ 工具集 '{name}' 創建成功！"
        else:
            return f"✗ 創建失敗：{response.text}"
    except Exception as e:
        return f"✗ 錯誤：{str(e)}"

def list_toolsets():
    """列出所有工具集"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/toolsets")
        toolsets = response.json()
        
        data = []
        for ts in toolsets:
            data.append([
                ts['id'][:8],
                ts['name'],
                ts['description'] or '',
                len(ts['tool_names']),
                "全局" if ts['is_global'] else "專用"
            ])
        
        return data
    except:
        return []

def get_toolset_details(toolset_id):
    """獲取工具集詳情"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/toolsets/{toolset_id}")
        return response.json()
    except:
        return {}
```

### 3.2 Agent 工具集分配介面

在 `web/app.py` 的 Agent 管理標籤中添加：

```python
with gr.TabItem("Agent 管理"):
    # ... 現有的 Agent 創建/編輯 UI ...
    
    gr.Markdown("### 工具集分配")
    
    agent_selector = gr.Dropdown(label="選擇 Agent")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("#### 已分配的工具集")
            assigned_toolsets = gr.DataFrame(
                headers=["名稱", "工具數量", "來源"],
                label="已分配"
            )
        
        with gr.Column():
            gr.Markdown("#### 可分配的工具集")
            available_toolsets = gr.Dropdown(label="選擇工具集")
            assign_btn = gr.Button("分配", variant="primary")
            remove_btn = gr.Button("移除", variant="stop")
    
    gr.Markdown("#### Agent 可用工具預覽")
    available_tools_preview = gr.DataFrame(
        headers=["工具名稱", "描述", "來源"],
        label="可用工具"
    )
    
    # 事件處理
    agent_selector.change(
        fn=load_agent_toolsets,
        inputs=agent_selector,
        outputs=[assigned_toolsets, available_tools_preview]
    )
    
    assign_btn.click(
        fn=assign_toolset,
        inputs=[agent_selector, available_toolsets],
        outputs=assigned_toolsets
    )
```

### 3.3 整合到主應用

在 `web/app.py` 中：

```python
from web.toolset_management import create_toolset_ui

def main():
    with gr.Blocks(title="AI 辯論平台") as app:
        gr.Markdown("# AI 辯論平台")
        
        with gr.Tabs():
            # 現有標籤
            create_debate_tab()
            create_agent_management_tab()
            
            # 新增：工具集管理
            create_toolset_ui()
            
            # 其他標籤...
    
    app.launch(server_name="0.0.0.0", server_port=7860)
```

---

## 📊 實現進度總結

| 任務 | 狀態 | 完成度 | 預計時間 |
|------|------|--------|----------|
| ToolSet API 端點 | ✅ 完成 | 100% | 30 分鐘 |
| 更新 debate_cycle.py | 📝 指南 | 0% | 30 分鐘 |
| Gradio 前端 | 📝 指南 | 0% | 2-3 小時 |

---

## 🚀 下一步行動

### 立即執行（需要解決資料庫問題）

1. **刪除舊資料庫**
   ```bash
   rm data/debate.db
   ```

2. **重啟服務**
   ```bash
   docker-compose restart api worker
   ```

3. **初始化全局工具集**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/toolsets/initialize-global"
   ```

4. **測試 ToolSet API**
   ```bash
   curl "http://localhost:8000/api/v1/toolsets"
   ```

### 短期（1-2 小時）

1. 實現 `debate_cycle.py` 的動態工具列表
2. 修改 Agent 創建邏輯，添加 ID 屬性
3. 測試辯論流程

### 中期（2-3 小時）

1. 實現 Gradio 工具集管理介面
2. 實現 Agent 工具集分配介面
3. 整合測試

---

## 📁 相關文件

- ✅ `api/models.py` - ToolSet, AgentToolSet Models
- ✅ `api/toolset_schemas.py` - Pydantic Schemas
- ✅ `api/toolset_service.py` - 業務邏輯
- ✅ `api/toolset_routes.py` - API 端點（獨立文件）
- ✅ `api/main.py` - 整合的 API 端點
- ✅ `api/tool_registry.py` - 擴展方法
- ✅ `TOOLSET_ARCHITECTURE.md` - 架構文檔
- 📝 `worker/debate_cycle.py` - 待修改
- 📝 `web/toolset_management.py` - 待創建
- 📝 `web/app.py` - 待更新

---

## 💡 重要提醒

1. **資料庫遷移**：需要創建 `toolsets` 和 `agent_toolsets` 表
2. **Agent ID**：需要確保 Agent 有 ID 屬性才能關聯工具集
3. **全局工具集**：系統啟動時應自動創建
4. **向後兼容**：沒有分配工具集的 Agent 應使用全局工具集

---

## 🎯 成就總結

今日完成：
1. ✅ TEJ 工具調用修正
2. ✅ Agent 管理 API（90%）
3. ✅ ToolSet 架構設計
4. ✅ ToolSet API 實現
5. ✅ 詳細實現指南

總計：5 個主要功能模塊！
