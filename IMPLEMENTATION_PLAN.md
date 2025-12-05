# AI 辯論平台 - Agent 管理與團隊組建實現計劃

## 當前狀態評估

### ✅ 已完成
1. **TEJ 工具整合**
   - 25 個 TEJ 工具已註冊並可用
   - 統一工具配置架構（`worker/tool_config.py`）
   - 主席和 Agent 使用一致的工具列表

2. **工具調用發現**
   - LLM 確實嘗試調用工具（Ollama `tool_calls` 格式）
   - 問題：解析邏輯不匹配 Ollama 的輸出格式

### ❌ 待修正
1. **工具調用解析**
   - 需要支持 Ollama 的 `tool_calls` 格式
   - 需要支持純 JSON 格式（向後兼容）

2. **前端功能缺失**
   - 無 Agent 管理介面
   - 無團隊組建介面
   - 主席是硬編碼的

---

## 實現計劃

### 階段 1：修正工具調用解析（優先級：🔴 最高）

**目標**：讓 Agent 能夠成功調用 TEJ 工具

**任務**：
1. 修改 `worker/debate_cycle.py` 的工具調用解析邏輯
   - 支持 Ollama `tool_calls` 格式
   - 支持純 JSON 格式
   - 添加詳細的調試日誌

2. 修改 `worker/llm_utils.py` 的 LLM 調用邏輯
   - 檢查 Ollama 是否支持 tools 參數
   - 如果支持，傳遞工具定義
   - 如果不支持，使用 prompt 引導

3. 測試驗證
   - 創建測試辯論
   - 確認 Agent 成功調用 `tej.stock_price`
   - 確認獲得真實數據

**預計時間**：1-2 小時

---

### 階段 2：Agent 管理 API（優先級：🟡 高）

**目標**：提供 Agent 的 CRUD 操作

**資料庫 Schema**：
```sql
CREATE TABLE agents (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50),  -- 'debater', 'chairman', 'analyst'
    specialty TEXT,    -- 專長描述
    system_prompt TEXT,
    config JSON,       -- 其他配置
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**API 端點**：
- `GET /api/v1/agents` - 列出所有 Agent
- `POST /api/v1/agents` - 創建 Agent
- `GET /api/v1/agents/{id}` - 獲取 Agent 詳情
- `PUT /api/v1/agents/{id}` - 更新 Agent
- `DELETE /api/v1/agents/{id}` - 刪除 Agent

**預計時間**：2-3 小時

---

### 階段 3：團隊組建 API（優先級：🟡 高）

**目標**：支持靈活的團隊配置

**資料庫 Schema**：
```sql
CREATE TABLE debate_teams (
    id VARCHAR(36) PRIMARY KEY,
    debate_id VARCHAR(36),
    team_name VARCHAR(100),
    team_side VARCHAR(20),  -- 'pro', 'con', 'neutral'
    agent_ids JSON,         -- ['agent-id-1', 'agent-id-2', 'agent-id-3']
    created_at TIMESTAMP
);

CREATE TABLE debate_configs (
    id VARCHAR(36) PRIMARY KEY,
    topic TEXT,
    chairman_id VARCHAR(36),  -- Agent ID
    rounds INT,
    enable_cross_examination BOOLEAN,
    created_at TIMESTAMP
);
```

**API 端點**：
- `POST /api/v1/debates/config` - 創建辯論配置
  ```json
  {
    "topic": "...",
    "chairman_id": "agent-uuid",
    "teams": [
      {
        "name": "正方團隊",
        "side": "pro",
        "agent_ids": ["agent-1", "agent-2", "agent-3"]
      },
      {
        "name": "反方團隊",
        "side": "con",
        "agent_ids": ["agent-4", "agent-5"]
      }
    ],
    "rounds": 5,
    "enable_cross_examination": true
  }
  ```

**預計時間**：3-4 小時

---

### 階段 4：Gradio 前端實現（優先級：🟢 中）

**目標**：提供直觀的 UI 進行 Agent 和團隊管理

#### 4.1 Agent 管理頁面

**功能**：
1. **Agent 列表**
   - 顯示所有 Agent（表格形式）
   - 篩選：角色、專長
   - 搜尋：名稱

2. **創建 Agent**
   - 表單：名稱、角色、專長、系統 Prompt
   - 驗證：必填欄位
   - 預覽：顯示配置

3. **編輯 Agent**
   - 選擇 Agent → 載入資料
   - 修改 → 保存

4. **刪除 Agent**
   - 確認對話框
   - 檢查：是否被使用中的辯論引用

**UI 組件**：
```python
with gr.TabItem("Agent 管理"):
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 創建新 Agent")
            agent_name = gr.Textbox(label="名稱")
            agent_role = gr.Dropdown(
                choices=["debater", "chairman", "analyst"],
                label="角色"
            )
            agent_specialty = gr.Textbox(label="專長", lines=3)
            agent_system_prompt = gr.Code(
                label="系統 Prompt",
                language="text"
            )
            create_agent_btn = gr.Button("創建 Agent")
            
        with gr.Column(scale=2):
            gr.Markdown("## Agent 列表")
            agents_table = gr.DataFrame()
            refresh_agents_btn = gr.Button("刷新")
            
            gr.Markdown("## 操作")
            selected_agent = gr.Dropdown(label="選擇 Agent")
            edit_agent_btn = gr.Button("編輯")
            delete_agent_btn = gr.Button("刪除")
```

**預計時間**：4-5 小時

#### 4.2 團隊組建頁面

**功能**：
1. **選擇主席**
   - Dropdown：所有 chairman 角色的 Agent

2. **組建團隊**
   - 添加團隊（最多 3 個）
   - 每個團隊：
     - 團隊名稱
     - 立場（正方/反方/中立）
     - 選擇 Agent（最多 3 個）

3. **配置辯論**
   - 輪數
   - 啟用交叉質詢

4. **預覽配置**
   - 顯示完整配置
   - 驗證：至少 2 個團隊

5. **啟動辯論**
   - 提交配置
   - 顯示 Task ID

**UI 組件**：
```python
with gr.TabItem("辯論配置"):
    gr.Markdown("## 辯論主題")
    debate_topic = gr.Textbox(label="辯論主題")
    
    gr.Markdown("## 選擇主席")
    chairman_dropdown = gr.Dropdown(label="主席")
    
    gr.Markdown("## 組建團隊")
    with gr.Accordion("正方團隊", open=True):
        pro_team_name = gr.Textbox(label="團隊名稱", value="正方")
        pro_agents = gr.Dropdown(
            label="選擇 Agent（最多 3 個）",
            multiselect=True
        )
    
    with gr.Accordion("反方團隊", open=True):
        con_team_name = gr.Textbox(label="團隊名稱", value="反方")
        con_agents = gr.Dropdown(
            label="選擇 Agent（最多 3 個）",
            multiselect=True
        )
    
    with gr.Accordion("第三方團隊（可選）", open=False):
        neutral_team_name = gr.Textbox(label="團隊名稱")
        neutral_agents = gr.Dropdown(
            label="選擇 Agent（最多 3 個）",
            multiselect=True
        )
    
    gr.Markdown("## 辯論設定")
    rounds = gr.Slider(minimum=1, maximum=10, value=3, label="輪數")
    enable_cross = gr.Checkbox(label="啟用交叉質詢", value=True)
    
    gr.Markdown("## 配置預覽")
    config_preview = gr.JSON(label="配置")
    
    start_debate_btn = gr.Button("開始辯論", variant="primary")
    debate_result = gr.Textbox(label="結果")
```

**預計時間**：5-6 小時

---

### 階段 5：證據驗證機制（優先級：🔵 低）

**目標**：實現交叉質詢和證據驗證

**功能**：
1. **證據追蹤**
   - 記錄每次工具調用
   - 保存工具返回的原始數據
   - 記錄引用來源

2. **交叉質詢環節**
   - 在每輪辯論後
   - 對方可以質疑證據
   - 要求提供原始數據或重新驗證

3. **證據可信度評分**
   - 來源可信度（TEJ > 網頁搜尋）
   - 數據新鮮度
   - 是否可驗證

**資料庫 Schema**：
```sql
CREATE TABLE evidence (
    id VARCHAR(36) PRIMARY KEY,
    debate_id VARCHAR(36),
    round_num INT,
    agent_id VARCHAR(36),
    tool_name VARCHAR(100),
    tool_params JSON,
    tool_result JSON,
    credibility_score FLOAT,
    challenged BOOLEAN,
    created_at TIMESTAMP
);
```

**預計時間**：6-8 小時

---

## 總時間估算

- 階段 1：1-2 小時（立即執行）
- 階段 2：2-3 小時
- 階段 3：3-4 小時
- 階段 4：9-11 小時
- 階段 5：6-8 小時

**總計**：21-28 小時

---

## 優先順序建議

1. **立即執行**：階段 1（修正工具調用）
2. **本週完成**：階段 2 + 階段 3（API 層）
3. **下週完成**：階段 4（前端）
4. **未來迭代**：階段 5（證據驗證）

---

## 技術債務與改進

1. **LLM 工具調用標準化**
   - 考慮使用 LangChain 或 LlamaIndex
   - 統一不同 LLM 的工具調用格式

2. **Agent 配置管理**
   - 支持 Agent 版本控制
   - Agent 性能追蹤

3. **辯論流程優化**
   - 支持更複雜的辯論格式
   - 動態調整輪數

4. **前端體驗**
   - 實時辯論進度顯示
   - 辯論回放功能
   - 數據可視化

---

## 下一步行動

✅ **立即執行**：修正工具調用解析邏輯
- 修改 `worker/debate_cycle.py`
- 支持 Ollama `tool_calls` 格式
- 測試驗證

📝 **本週規劃**：
- 設計 Agent 資料庫 Schema
- 實現 Agent CRUD API
- 實現團隊配置 API

🎨 **下週規劃**：
- 實現 Gradio 前端
- 整合測試
- 文檔撰寫
