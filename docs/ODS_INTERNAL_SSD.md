# Open Data Scientist - Internal System Design Document (SSD)

## 1. 簡介

本文件定義了如何將 **Open Data Scientist (ODS)** 的核心能力（ReAct 推理、Python 程式碼執行、數據分析）整合進 Agentscope Debate 系統，作為一個專門的「數據科學家 Agent」。

此設計旨在提供一個安全、可擴展且能產生高品質分析報告的數據輔助角色，支援辯論過程中的數據佐證需求。

---

## 2. 系統架構

### 2.1 核心組件

```mermaid
graph TD
    User[辯手 Agent / 主席 Agent] -->|數據請求 (Query)| ODS[DataScientistAgent]
    
    subgraph ODS_Internal [Data Scientist Agent 內部]
        ReAct[ReAct 推理引擎] -->|生成程式碼| Sandbox[Python 沙箱環境]
        Sandbox -->|執行結果/錯誤| ReAct
        ReAct -->|自我修正/下一步| ReAct
    end
    
    ODS -->|最終報告 (Text + Charts)| User
    
    subgraph External_Resources [外部資源]
        TEJ[TEJ API]
        OpenData[Open Data Source]
    end
    
    Sandbox -.->|數據獲取| External_Resources
```

### 2.2 角色職責

| 角色 | 職責描述 |
|------|----------|
| **DataScientistAgent** | 接收自然語言查詢，轉化為數據分析任務，生成並執行 Python 程式碼，最終產出分析報告。 |
| **PythonToolAdapter** | 提供安全的程式碼執行環境，攔截並處理繪圖請求，管理依賴庫。 |
| **Chairman** | 識別辯論中的數據需求，將任務分派給 DataScientistAgent，並驗收報告品質。 |

---

## 3. 詳細設計

### 3.1 DataScientistAgent (`worker/data_scientist.py`)

繼承自基礎 Agent，但具備特殊的 `reply` 邏輯以實作 ReAct 循環。

- **System Prompt**: 強調其作為數據科學家的身份，要求其必須透過編寫程式碼來回答問題，而非依賴內部知識。
- **ReAct Loop**:
    1.  **Thought**: 分析問題，決定下一步行動（寫程式、搜尋數據、結束任務）。
    2.  **Action**: 生成 Python 程式碼區塊。
    3.  **Observation**: 接收程式碼執行結果（stdout, stderr, 圖片路徑）。
    4.  **Repeat**: 根據執行結果進行修正或進一步分析，直到得出結論。

### 3.2 Python 執行環境 (Sandbox)

採用 **本地 Docker 容器** 方案以確保隔離性與一致性。

- **映像檔**: 基於官方 Python 映像檔，預裝 `pandas`, `numpy`, `matplotlib`, `seaborn`, `scikit-learn`, `requests` 等常用庫。
- **掛載**: 掛載一個臨時目錄用於輸出圖片與報告檔案。
- **安全性**: 限制網路存取（僅允許白名單 API，如 TEJ），限制執行時間與記憶體用量。

### 3.3 輸出格式規範

ODS 的最終輸出必須包含兩部分：

1.  **執行摘要 (Executive Summary)**: 針對問題的直接回答，使用自然語言。
2.  **分析報告 (Analysis Report)**: 
    - 數據來源說明
    - 分析方法
    - 關鍵發現
    - **圖表連結**: 引用生成的圖表檔案 (Markdown 格式: `![Chart](path/to/chart.png)`)

---

## 4. 整合流程

### 4.1 觸發場景

1.  **辯手主動請求**: 辯手在建構論點時，透過工具調用請求「查詢 X 公司的獲利趨勢」。
2.  **主席被動觸發**: 主席在審核辯論時，發現某方數據存疑，指派 ODS 進行「驗證 Y 數據的真實性」。

### 4.2 互動序列圖

```mermaid
sequenceDiagram
    participant D as Debater
    participant C as Chairman
    participant ODS as DataScientist
    participant E as ExecutionEnv

    D->>C: 提出論點 (含數據)
    C->>C: 判斷需要數據驗證
    C->>ODS: 任務: "驗證 X 公司 2023 年營收是否為 Y"
    
    loop ReAct Cycle
        ODS->>ODS: 思考: 需要查詢 TEJ 資料庫
        ODS->>E: 執行代碼 (import tejapi...)
        E-->>ODS: 返回 DataFrame (2023 營收數據)
        ODS->>ODS: 思考: 數據不符，需繪製趨勢圖
        ODS->>E: 執行代碼 (plt.plot...)
        E-->>ODS: 返回圖片路徑 (./charts/rev_trend.png)
    end
    
    ODS-->>C: 回報: "數據不符，實際為 Z。附圖：營收趨勢"
    C->>D: 駁回論點，要求修正
```

---

## 5. 待辦事項 (Implementation Checklist)

- [ ] **基礎設施**:
    - [ ] 建立 `worker/data_scientist.py`
    - [ ] 建立 Dockerfile for ODS Sandbox
- [ ] **工具開發**:
    - [ ] 升級 `adapters/python_tool_adapter.py` 支援 Docker 執行
    - [ ] 實作 Matplotlib 圖片攔截與儲存機制
- [ ] **流程整合**:
    - [ ] 修改 `Chairman` Prompt 加入 ODS 調度指令
    - [ ] 在 `worker/debate_cycle.py` 中接入 ODS 節點
- [ ] **測試**:
    - [ ] 單元測試: Python 執行與錯誤處理
    - [ ] 整合測試: 完整辯論流程中的數據查詢

## 6. 技術限制與風險

- **執行延遲**: Docker 啟動與程式碼執行可能耗時較長，需設定合理的 Timeout。
- **幻覺風險**: 模型可能生成錯誤的 API 呼叫或不存在的庫函數，需透過 ReAct 的自我修正機制緩解。
- **數據隱私**: 若涉及敏感數據，需確保 Docker 容器執行後完全銷毀數據。
