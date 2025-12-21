# 開發者指南：財務引擎、讀取器與 AI 整合 (Dev Guide)

本文件說明如何維護系統的計算核心與語義審計邏輯。

## 1. 核心模組架構

*   **`worker/metrics_engine_dcf.py`**:
    *   負責硬性數學運算 (DCF Scenarios, EVA, ROIC)。
    *   包含 **`MetricsEngineDCF_AI`** 類別。
*   **`worker/advanced_financial_reader.py`**:
    *   負責 **`AdvancedFinancialReader`** 類別。
    *   實作趨勢判定 (`↑/↓/→`) 與行業平均對比邏輯。
*   **`worker/sec_edgar_tool.py`**:
    *   負責數據預處理,將 raw XBRL Tags 映射為上述引擎所需的結構化 DataFrame。

## 2. 數據映射 (Data Mapping) 擴充

若要支持更多 XBRL 標籤：
1. 修改 `sec_edgar_tool.py` 中的 `mapping` 字典。
2. 確保 `mapping` 鍵名與引擎構造函數中的預期欄位名一致。

## 3. 語義分析接口

智能體透過 `simple_reading` 字段獲取初步的 AI 財務解讀。若要修改解讀邏輯（例如改變「毛利率高」的判定閾值）,請修改 `AdvancedFinancialReader.interpret_value` 方法。

## 4. 台股適配 (TW Adaptation)

台股目前透過 `chinatimes.*` 獲取數據。智能體系統提示詞已包含「白話對應關係」,開發者應確保 `Quant Analyst` 提取的數據項能正確餵入 `AdvancedFinancialReader.run_advanced_reader`。

## 5. 迴歸測試

更新引擎後,必須執行：
- `python verify_sec_tool.py`: 驗證美股 XBRL 鏈條。
- `python verify_advanced_reader.py`: 驗證讀取器邏輯（含趨勢判斷）。
