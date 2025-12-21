"""
MOPS Financial Data Client (Institutional Workflow)

This script implements the institutional step-by-step fetching guide for MOPS:
1. Entry: Standard Consolidated Financial Statements (IFRS)
2. Mapping: Big Three items to Metrics Engine
3. Deep Dive: Triggering Note Extraction for large items
"""

import requests
import pandas as pd
from typing import Dict, Any, List

class MOPSInstitutionalClient:
    def __init__(self):
        # MOPS 核心採 IFRSs 後之合併報表入口
        self.entry_urls = {
            "balance_sheet": "https://mops.twse.com.tw/mops/web/t164sb03",
            "income_statement": "https://mops.twse.com.tw/mops/web/t164sb04",
            "cash_flow": "https://mops.twse.com.tw/mops/web/t164sb05"
        }

    def get_big_three_mapping(self, symbol: str, year: int, season: int) -> Dict[str, Any]:
        """
        Step 1: 先大後小 (The Big Three Sweep)
        此方法定義如何將 MOPS 的 HTML/JSON 欄位對應至估值引擎。
        """
        # 實際實作中，這會模擬 POST 請求至上述 URL 並解析表格
        print(f"ACTION: Standardizing MOPS mapping for {symbol} {year}Q{season}")
        
        # 映射標準對照
        mapping_logic = {
            "Revenue": "營業收入合計",
            "GrossProfit": "營業毛利（毛損）",
            "EBIT": "營業利益（損失）",
            "NetIncome": "本期淨利（淨損）",
            "Equity": "權益總計",
            "Debt": "負債總計",
            "OCF": "營業活動之淨現金流入（流出）"
        }
        
        return mapping_logic

    def trigger_notes_audit(self, financials: Dict[str, float]) -> List[str]:
        """
        Step 2: 異常鎖定 (Anomaly Detection)
        """
        audit_targets = []
        if financials.get("Inventory", 0) > financials.get("TotalAssets", 0) * 0.1:
            audit_targets.append("Inventory")
        if financials.get("ShortTermDebt", 0) > financials.get("Cash", 0):
            audit_targets.append("Liquidity Risk (ShortTermDebt)")
        return audit_targets

def run_mops_extraction_workflow(symbol: str):
    client = MOPSInstitutionalClient()
    print(f"=== MOPS Institutional Extraction Flow: {symbol} ===")
    
    # 1. 執行大項掃描
    mapping = client.get_big_three_mapping(symbol, 2024, 3)
    print(f"MAP: Found {len(mapping)} standard fields for MetricsEngine.")
    
    # 2. 模擬異常檢測 (假設數據)
    mock_fin = {"Inventory": 1000, "TotalAssets": 5000, "Cash": 200, "ShortTermDebt": 500}
    targets = client.trigger_notes_audit(mock_fin)
    
    # 3. 附註穿透指引
    for t in targets:
        print(f"VETO/AUDIT: Target [{t}] triggered. Action: Navigate to MOPS '電子書' and search for Note.")

    print("SUCCESS: MOPS Extraction Pipeline Ready.")

if __name__ == "__main__":
    run_mops_extraction_workflow("2330")
