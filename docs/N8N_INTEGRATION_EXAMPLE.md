# 如何將 n8n Webhook 加入為 AI 辯論平台的工具

本指南演示如何將一個 n8n workflow (Webhook) 註冊為 Agent 可用的工具。

## 場景假設
假設您有一個 n8n workflow，功能是查詢最新的 Google News。
- **Webhook URL**: `https://your-n8n-instance.com/webhook/search-news`
- **Method**: `POST`
- **輸入參數**: 需要一個 JSON Body `{"keyword": "..."}`
- **輸出**: 返回新聞列表 JSON

## 操作步驟

1.  打開 AI 辯論平台前端 (`http://localhost:7860`)。
2.  切換到 **「🔧 自定義工具」** 標籤頁。

### 填寫欄位

*   **工具名稱**: `n8n_news_search` (建議使用英文，下劃線分隔)
*   **工具類型**: `http`
*   **工具組**: `browser_use` (這樣 Agent 在需要搜尋時會自動選擇它)
*   **API URL**: `https://your-n8n-instance.com/webhook/search-news`
*   **HTTP Method**: `POST`
*   **Headers (JSON)**: 
    ```json
    {
      "Content-Type": "application/json",
      "Authorization": "Bearer YOUR_N8N_TOKEN"
    }
    ```
    *(如果您的 n8n 設置了 Webhook 驗證，請在此填入)*

*   **參數 Schema (JSON Schema)**:
    這是告訴 Agent 如何使用此工具的關鍵。
    ```json
    {
      "type": "object",
      "properties": {
        "keyword": {
          "type": "string",
          "description": "要搜尋的新聞關鍵字，例如 '台積電 營收'"
        }
      },
      "required": ["keyword"]
    }
    ```

### 自動生成描述

1.  填寫完上述信息後，點擊 **「✨ 自動生成描述」** 按鈕。
2.  系統會自動分析 Schema，並生成類似如下的描述：
    > 此工具用於通過 n8n 搜索 Google News。Agent 應在需要獲取最新新聞資訊時使用。關鍵參數為 `keyword`，用於指定搜尋主題。

### 完成註冊

1.  點擊 **「➕ 新增工具」**。
2.  系統提示「Tool 'n8n_news_search' created successfully!」。
3.  現在，當辯論開始且 Agent 需要搜尋新聞時，它就會自動調用這個 n8n webhook，並將 `keyword` 傳遞給您的 workflow。

## 背後原理
平台會自動將 Agent 的調用參數 (如 `{"keyword": "AI"}`) 作為 JSON Body 發送給 n8n (`POST` 請求)，並將 n8n 返回的 JSON 數據直接作為「證據」提供給 Agent。