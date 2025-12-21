# AI 語義分析與估值引擎整合指南 (AI Valuation Integration)

本系統整合了「Python 數學引擎」與「AI 語義審計」,確保估值流程具備法醫級的嚴密性。

## 1. 三階段執行流程 (The 3-Step Chain)

系統嚴格遵循以下執行階段，杜絕敘事與數字脫鉤：

### Phase 1: 數字指標計算 (Metrics Engine)
*   **引擎**: `MetricsEngineDCF_AI` 與 `AdvancedFinancialReader`。
*   **輸出**: 產出 EVA、ROIC、趨勢標籤 (↑/↓) 與 行業對比結果。
*   **保險絲**: 自動偵測 `ROIC < WACC` 的價值毀損狀態。

### Phase 2: AI 語義審計 (Semantic Audit)
*   **輸入**: Phase 1 的數字結果 + MD&A/新聞文字。
*   **核心功能**: 
    *   **敘事偏差偵測**: 比對「管理層口頭承諾」與「增量 ROIC」的真實表現。
    *   **語氣識別**: 將 MD&A 的樂觀/謹慎情緒納入考量。
*   **偏差評等**: LOW (一致) / MEDIUM (預期領先) / HIGH (嚴重脫鉤)。

### Phase 3: 綜合報告生成
*   結合數據事實與語義洞察，產出具備「信心評分」的投資報告。

## 2. 退化模式 (Degraded Mode) 規範

當結構化 XBRL 數據不可得時，系統進入退化模式：
1.  **強制標記**: 發言必須包含 `[DEGRADED MODE - LLM ESTIMATED]`。
2.  **數據補全**: 使用搜尋工具獲取營收、淨利等基礎項目。
3.  **風險權重**: 自動擴大 DCF 估值區間（如：基準情境權重下修，悲觀情境權重上調）。

## 3. 核心指標對應表

| 商業直覺名稱 | 專業財務指標 | 良好基準 |
| :--- | :--- | :--- |
| 產品好不好賺 | 毛利率 (Gross Margin) | > 40% |
| 賺錢效率 | 利益率 (Operating Margin) | 穩定增長 |
| 口袋裡的現金 | 自由現金流 (FCF) | > 0 |
| 超額收益能力 | EVA (Economic Value Added) | > 0 |
| 護城河擴張度 | Incremental ROIC | > WACC |
