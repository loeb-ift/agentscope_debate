# 瀏覽工具治理與記憶優化指南 (Browser Tool Governance & Memory Optimization)

本平台整合了基於 Playwright 的網頁瀏覽工具 (`browser.browse`)。為了兼顧「深入調查」的深度與「成本控管」的精準，系統實作了兩層防禦機制：**主席治理閘口 (Governance Gate)** 與 **自動摘要層 (Summarization Layer)**。

## 1. 工具定義與全局可用性

### 核心工具
- **`browser.browse`**: 瀏覽目標 URL 並獲取文字內容。
- **`browser.page_source`**: 獲取目標 URL 的完整 HTML 原始碼。

### 可用性
這些工具被標記為 **全局核心工具**。無論辯題為何，所有 Agent 在初始化時都會在「推薦工具列表」中看到它們。

---

---

## 2. 數據信任與優先級體系 (Data Trust & Priority Hierarchy)

在選擇檢索工具前，Agent 必須遵循 **「內部優先、外部審慎」** 的原則。系統根據數據來源的公信力與成本，將工具分為不同優先級：

### 2.1 L1: 內部核心工具 (High Trust, No Gate)
- **代表工具**: `chinatimes.*` (時報資訊系列)。
- **特點**:
    - **免准核**: 不需要向主席申請，可直接調用。
    - **最高權限**: 系統認定其數據具備事實锚定效力。
    - **強制優先**: Agent 應優先獲取內部報價與財報，僅在內部數據缺失時才轉向外部。

### 2.2 L2: 專業分析與全球驗證工具
- **代表工具**: `financial.pdr_reader` (Pandas-DataReader/Stooq), `financial.technical_analysis`, `twse.stock_day`。
- **特點**:
    - 用於全球宏觀數據檢索或對原始報價進行量化分析。
    - **公開透明**: 可用於驗證 L1 數據的異常點。

### 2.3 L3: 受限網頁瀏覽工具 (Governance Gated)
- **代表工具**: `browser.browse`, `browser.page_source`。
- **治理邏輯**: 由於成本極高，系統強制執行 **「主席准核機制」**，並增加以下實體限制：

#### 核心規則：
1. **搜尋先行 (Discovery Only)**: 只能瀏覽搜尋結果中出現過的 URL。
2. **一搜一付 (Search-Browse Quota)**: 每次成功搜尋獲得 1 點瀏覽配額。
3. **策略性選擇 (Strategic Selection)**: 必須在 justification 中說明為何官方/內部數據不足以支持論點。

### 2.4 L4: 測試版備援工具 (Beta Only)
- **代表工具**: `tej.*`。
- **治理邏輯**: 僅作最後備援，不可作為首要證據點。

---

## 3. 網頁瀏覽准核流程 (Approval Flow)
1. **Agent 申請**: 填寫 `justification` 参数。
2. **預檢 (Pre-check)**: 系統檢查 Quota 與 Discovery 白名單。
3. **主席裁決**: 主席根據「內部數據是否已窮盡」與「邊際效益」評估是否 `approve`。

---

## 3. 第二層防禦：記憶管理與自動摘要 (Memory Opt)

網頁內容通常包含大量雜訊且長度極長，直接存入 Agent 的 Working Memory 會導致 **LLM Context Window 溢出** 或 **關鍵論點遺忘**。

### 優化機制：
- **觸發條件**: 任何來自 `browser.*` 的結果，或長度超過 **2000 字元** 的字串。
- **極限壓縮**: 系統會調用專用的高效能 LLM 進行摘要，要求：
    - 保留所有關鍵事實、日期、股價及數據。
    - 刪除廣告、導覽列及不相關資訊。
    - 將長度控制在 **800 字** 以內。
- **證據共存**:
    - **Agent 上下文**: 僅持有摘要後的精簡內容。
    - **證據庫 (Evidence Lifecycle)**: OSU 磁碟與資料庫中仍保留 **完整原始內容** 以供後續報告生成或人工複核。

---

## 4. 監控與日誌

在 Gradio UI 的「實時戰況」中，您可以透過日誌類型追蹤執行過程：
- **Governance**: 顯示攔截訊息。
- **Agent**: 顯示辯手提出的理由。
- **Chairman**: 顯示核准/駁回結果。
- **System**: 顯示「正在為龐大結果進行優化與摘要」的進度。

---

## 5. 開發者參考

### 標記受限工具
在 `api/tool_registry.py` 註冊時，透過 `requires_approval=True` 即可將任何 MCP 或自定義工具納入此治理框架：

```python
tool_registry.register_mcp_adapter(browser_adapter, prefix="browser", requires_approval=True)
```

### 修改摘要邏輯
摘要提示詞 (Prompt) 位於 `worker/debate_cycle.py` 的 `_summarize_content` 私有方法中。
