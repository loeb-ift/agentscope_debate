# Open Data Scientist 整合規劃

## 目標
將 `togethercomputer/open-data-scientist` 的核心能力（ReAct 推理 + Python 程式碼執行 + 數據分析）整合至 Agentscope Debate 系統中，作為一個專門的「數據科學家」角色。

## 核心組件分析 (參照 `codeagent.py`)

1.  **推理模型**: DeepSeek-V3 / Together AI (需要低 Temperature 以確保程式碼生成品質)。
2.  **執行環境**: 
    - 目前選項 A: 本地 Docker (安全、免費、需安裝)
    - 目前選項 B: Together Code Interpreter (方便、需 API Key)
3.  **依賴庫**: `pandas`, `numpy`, `scikit-learn`, `matplotlib`, `seaborn`, `rich` (用於格式化輸出)。

## 架構設計

### 1. 新增 Agent: `DataScientistAgent`
- **位置**: `worker/data_scientist.py`
- **職責**: 接收數據查詢或分析請求，編寫並執行 Python 程式碼，回傳分析結果（文本 + 圖表路徑）。
- **繼承**: 繼承自基礎 Agent 類別，但覆寫 `reply` 方法以實作 ReAct 循環 (Thought -> Code -> Observation -> Answer)。

### 2. 增強工具: `PythonToolAdapter`
- **位置**: `adapters/python_tool_adapter.py`
- **功能擴充**:
    - 支援 `matplotlib` 繪圖並自動儲存圖片到指定目錄。
    - 支援 `pandas` DataFrame 的顯示優化。
    - 增加安全性檢查 (沙箱機制)。

### 3. 整合至 Debate 流程
- **Chairman 角色**: 新增邏輯以識別何時需要「數據佐證」。
- **訊息流**: 
    - Debater -> (請求數據) -> Chairman -> DataScientist
    - DataScientist -> (分析報告) -> Chairman -> Debater

## 待確認事項
1. **執行環境**: Local Docker vs Cloud?
2. **觸發機制**: 被動回應 vs 主動介入?
