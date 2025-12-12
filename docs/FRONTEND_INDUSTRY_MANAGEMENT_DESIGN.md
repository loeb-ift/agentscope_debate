# 產業鏈前端管理介面設計 (Industry Chain Management Frontend Design)

本文件描述如何在現有的 Gradio 前端 (`web/app.py`) 中新增「產業鏈管理」功能，以視覺化方式呈現與管理公司及其上下游關係。

## 1. 使用者介面 (UI) 設計

將在主介面新增一個 Tab：**⛓️ 產業鏈管理**。

### 1.1 子頁籤：產業地圖 (Industry Map)
提供樹狀或層級式視圖，讓使用者能宏觀瀏覽產業結構。

*   **控制區**：
    *   **選擇產業 (Sector Dropdown)**：列出所有產業類別 (如 "半導體", "生技醫療")。
    *   **刷新按鈕**：重新載入資料。
*   **顯示區**：
    *   使用 `gr.JSON` 或 `gr.HTML` 呈現樹狀結構。
    *   結構：`產業 -> 環節 (上/中/下) -> 公司列表`。
    *   顯示格式：`[代號] 公司名稱 (子分類)`。

### 1.2 子頁籤：公司列表與編輯 (Company List & Edit)
提供詳細的表格視圖，支援搜尋與編輯。

*   **篩選區**：
    *   **產業篩選**：Dropdown (Sector)。
    *   **環節篩選**：Dropdown (Stream: 上游/中游/下游)。
    *   **關鍵字搜尋**：Textbox (搜尋名稱或代號)。
*   **列表區**：
    *   `gr.DataFrame` 顯示公司列表。
    *   欄位：`ID`, `Name`, `Ticker`, `Sector`, `Group (Stream)`, `Sub-industry`.
*   **編輯區**：
    *   點擊或輸入 ID 載入公司資料。
    *   可修改欄位：`Industry Sector`, `Industry Group` (支援多選或文字輸入), `Sub-industry`.
    *   **保存按鈕**。

---

## 2. 後端 API 需求 (`api/internal_api.py`)

為了支援上述前端功能，需擴充 Internal API。

### 2.1 擴充 `GET /companies`
支援篩選參數：
*   `sector`: str (Exact match)
*   `group`: str (Fuzzy match, for "上游; 中游")
*   `sub_industry`: str (Fuzzy match)

### 2.2 新增 `GET /industry-tree`
返回聚合後的樹狀結構資料。
*   **Response**: `Dict[Sector, Dict[Stream, List[CompanySummary]]]`
*   **用途**：供前端「產業地圖」直接渲染，減少前端處理邏輯。

### 2.3 新增 `GET /sectors` (Optional)
返回所有唯一的 `industry_sector` 列表，供 Dropdown 使用。

---

## 3. 實作步驟

1.  **Backend**: 修改 `api/internal_api.py`，實作上述 API 變更。
2.  **Frontend**: 修改 `web/app.py`，新增 Tab 與相關 Gradio 元件及邏輯。