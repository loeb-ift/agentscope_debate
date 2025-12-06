# 工具集系統實現指南 (Tool Integration Guide)

本指南旨在確保新增工具時架構的一致性，特別是針對「工具組 (Tool Groups)」與「動態選擇 (Dynamic Selection)」機制。

---

## 1. 新增工具流程 (How to Add New Tools)

### 步驟 1: 實作 ToolAdapter
在 `adapters/` 目錄下新增工具適配器，繼承 `adapters.tool_adapter.ToolAdapter`。

```python
from adapters.tool_adapter import ToolAdapter

class MyNewTool(ToolAdapter):
    @property
    def name(self) -> str:
        return "my.new_tool"
    
    # ... 實作其他屬性與方法 ...
```

### 步驟 2: 註冊工具 (Register with Group)
在 `worker/celery_app.py` 中註冊工具時，**必須指定 `group` 參數**。

**有效的工具組 (Valid Groups):**
- `basic`: 基礎工具，默認啟用。
- `browser_use`: 網頁瀏覽相關 (SearXNG, DuckDuckGo)。
- `financial_data`: 金融數據相關 (TEJ, YFinance)。
- `data_analysis`: 數據分析相關。

```python
# worker/celery_app.py

from adapters.my_new_tool import MyNewTool

# 註冊到正確的組別
tool_registry.register(MyNewTool(), group="data_analysis")
```

### 步驟 3: 驗證
啟動 Worker，檢查日誌確認工具已註冊到指定組別。

---

## 2. 架構一致性機制 (Architecture Consistency)

### 工具組 (Tool Group)
- 所有工具必須歸屬於一個組別。
- Agent 可以通過 Meta-Tool `reset_equipped_tools(group="...")` 動態切換可用工具組。
- `api/tool_registry.py` 的 `list(groups=[...])` 方法支援按組別篩選工具。

### 動態選擇 (Dynamic Selection)
- 辯論開始時，Agent 會自動執行工具選擇流程 (`_agent_select_tools`)，根據題目與立場挑選最適合的工具。
- 開發者無需手動為每個 Agent 分配工具，只需確保工具描述 (`description`) 足夠清晰，讓 LLM 能準確判斷其用途。

---

## 3. 維護建議
- 定期檢查 `worker/celery_app.py`，確保所有工具都有明確的 `group` 分類。
- 若新增工具類別，請在 `api/tool_registry.py` 中更新相關邏輯（如需）。
