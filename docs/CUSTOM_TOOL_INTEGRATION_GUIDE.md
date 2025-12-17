# 自定義金融工具整合指南 (Custom Financial Tool Integration Guide)

本文件說明如何在現有的 **Symbol Utils + Price Proof Coordinator** 架構下，標準化地新增第三方金融數據工具（例如：Google Finance, Bloomberg, CoinGecko 等）。

## 架構概觀

系統採用 **「翻譯官 (Normalization) + 調度員 (Coordinator)」** 的模式：

1.  **翻譯官 (`worker/utils/symbol_utils.py`)**：負責將使用者輸入的股票代碼（如 `2330`）翻譯成各個平台專用的格式（如 TEJ 的 `2330`, Yahoo 的 `2330.TW`, 未來 Google 的 `TPE:2330`）。
2.  **調度員 (`worker/utils/price_proof_coordinator.py`)**：負責執行 fallback 邏輯，依序嘗試各個資料來源。

---

## 整合步驟 (Step-by-Step)

### 步驟 1：定義新工具的「代碼格式」 (Symbol Format)

首先確認新工具 API 要求的代碼格式。

| 工具名稱 | 範例代碼 (台積電) | 範例代碼 (元太 - 上櫃) | 備註 |
| :--- | :--- | :--- | :--- |
| **TEJ / TWSE (現有)** | `2330` | `8069` | 純數字代碼 |
| **Yahoo (現有)** | `2330.TW` | `8069.TWO` | 需後綴區分上市櫃 |
| **Google Finance (假設)** | `TPE:2330` | `TPE:8069` | `交易所:代碼` |
| **Bloomberg (假設)** | `2330 TT` | `8069 TT` | 透過空格分隔 |

### 步驟 2：擴充翻譯官 (`worker/utils/symbol_utils.py`)

修改 `normalize_symbol` 函式，新增一個 key 來存放新工具所需的格式。

```python
# worker/utils/symbol_utils.py

def normalize_symbol(symbol: str) -> Dict[str, Any]:
    # ... (前段解析邏輯不變) ...

    # 假設我們解析出了 base (2330) 和 market (TW)
    
    # === 新增自定義格式 ===
    # Example: Google Finance (TPE:xxxx)
    google_ticker = f"TPE:{base}" if result["market"] == "TW" else f"NASDAQ:{base}"
    
    # Example: Bloomberg (xxxx TT)
    bloomberg_ticker = f"{base} TT" if result["market"] == "TW" else f"{base} US"

    # 更新回傳字典
    result.update({
        "google_ticker": google_ticker,      # <--- 新增欄位
        "bloomberg_ticker": bloomberg_ticker # <--- 新增欄位
    })
    
    return result
```

### 步驟 3：實作 Adapter (`adapters/`)

在 `adapters/` 目錄下建立新的 Adapter，確保它遵循統一的介面（通常是 `invoke` 方法）。

**場景 A: 手刻 Python Client (適用於簡單 API)**

```python
# adapters/google_finance_adapter.py (範例)

class GoogleFinanceAdapter:
    def invoke(self, symbol: str, date: str):
        """
        Args:
            symbol: 必須是 TPE:2330 格式 (由 symbol_utils 提供)
            date: YYYY-MM-DD
        """
        # ... 實作 API 呼叫 ...
        return {"data": [...], "error": None}
```

**場景 B: 第三方 OpenAPI整合 (Advanced)**

若新工具提供 OpenAPI Spec (Swagger)，建議使用自動化方式生成或動態加載。

1.  **存放 Spec**: 將 JSON/YAML 放入 `data/openapi_specs/`。
2.  **通用 OpenAPI Adapter**: 我們可以使用 `openapi-python-client` 或動態請求。

```python
# adapters/generic_openapi_adapter.py

import requests

class GenericOpenAPIAdapter:
    def __init__(self, spec_url, base_url, api_key_name="Authorization"):
        self.base_url = base_url
        self.headers = {api_key_name: os.getenv("MY_TOOL_API_KEY")}
        
    def invoke(self, endpoint, params):
        # 這裡需要將我們內部的 symbol/date 轉換為該 OpenAPI 定義的參數名
        # 例如: 內部用 'symbol', 但對方 API 叫 'ticker_id'
        response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
        return response.json()
```

3.  **封裝成標準 Adapter**:

```python
class MyNewToolAdapter(GenericOpenAPIAdapter):
    def invoke(self, symbol, date):
        # 轉譯參數
        params = {
            "ticker": symbol,  # 從 symbol_utils 來
            "query_date": date
        }
        return super().invoke("stock/price", params)
```


### 步驟 4：註冊到調度員 (`worker/utils/price_proof_coordinator.py`)

將新工具加入 fallback 鏈中。建議依照資料可靠度與成本排序（官方源優先 > 付費源 > 免費爬蟲）。

```python
# worker/utils/price_proof_coordinator.py

# 1. Import
from adapters.google_finance_adapter import GoogleFinanceAdapter

class PriceProofCoordinator:
    def __init__(self):
        # ... (既有工具) ...
        self.google_tool = GoogleFinanceAdapter() # 2. 初始化

    def get_verified_price(self, symbol, date):
        # ...
        
        # 3. 從正規化結果取得對應格式
        # norm_res 是由 normalize_symbol 回傳的字典
        google_symbol = norm_res.get("google_ticker", symbol) 

        # ... (嘗試 TEJ) ...
        # ... (嘗試 TWSE) ...
        
        # 4. 加入 Fallback 鏈
        try:
            print(f"[PriceProof] Trying Google Finance with {google_symbol}...")
            res = self.google_tool.invoke(symbol=google_symbol, date=target_date)
            
            if self._validate_response(res):
                 return {
                    "status": "success",
                    "source": "Google Finance",
                    "price": res["data"][0]["close"],
                    # ...
                }
        except Exception as e:
            print(f"[PriceProof] Google Finance Failed: {e}")

        # ... (嘗試 Yahoo - 最後一道防線) ...
```

## 測試驗證

完成後，請務必執行 `diagnose_tickers.py` 進行測試，確認：

1.  `normalize_symbol` 正確輸出了新的 ticker 格式。
2.  `PriceProofCoordinator` 在前順位工具失敗時，能正確切換到新工具。
