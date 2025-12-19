import os
import sys
import json
import asyncio
# Ensure app root is in path
sys.path.insert(0, os.getcwd())

from api.tool_registry import tool_registry
from worker.tool_config import STOCK_CODES
from api.database import SessionLocal
from api.init_data import initialize_all

# Mock Configuration
TEST_COID = "6591" # 動力-KY
TEST_NAME = "動力-KY"

async def main():
    print(f"=== 🚀 開始工具鏈整合測試 (Target: {TEST_NAME} {TEST_COID}) ===")
    
    # 1. Initialize Registry (Load dynamic tools)
    print("\n[Step 1] 初始化工具註冊表...")
    db = SessionLocal()
    try:
        # Ensure tools are registered in DB and loaded
        initialize_all(db) 
        # But initialize_all registers to DB, not memory registry directly? 
        # api/main.py loads them. We need to mimic that.
        from adapters.searxng_adapter import SearXNGAdapter
        from adapters.duckduckgo_adapter import DuckDuckGoAdapter
        from adapters.yfinance_adapter import YFinanceAdapter
        from adapters.tej_adapter import (
            TEJCompanyInfo, TEJStockPrice, TEJMonthlyRevenue, TEJFinancialSummary, 
            TEJInstitutionalHoldings
        )
        
        # Register core adapters
        tool_registry.register(SearXNGAdapter())
        tool_registry.register(DuckDuckGoAdapter())
        tool_registry.register(YFinanceAdapter())
        tool_registry.register(TEJCompanyInfo())
        tool_registry.register(TEJStockPrice())
        tool_registry.register(TEJMonthlyRevenue())
        tool_registry.register(TEJFinancialSummary())
        tool_registry.register(TEJInstitutionalHoldings())
        
        # Also register Internal DB Tools (Need to import)
        from adapters.database_tool_adapter import SearchCompany, GetCompanyDetails
        tool_registry.register(SearchCompany())
        tool_registry.register(GetCompanyDetails())
        
    finally:
        db.close()
    
    print(f"✅ 工具註冊完成。可用工具數: {len(tool_registry.list_tools())}")

    # 2. Define Test Cases
    # Each case mimics an Agent's intent
    test_cases = [
        {
            "tool": "internal.search_company",
            "params": {"query": TEST_COID},
            "desc": "內部資料庫搜尋 (Standard)"
        },
        {
            "tool": "internal.search_company",
            "params": {"keyword": TEST_NAME},
            "desc": "內部資料庫搜尋 (Alias 'keyword')"
        },
        {
            "tool": "internal.get_company_details",
            "params": {"id": TEST_COID}, 
            "desc": "內部資料庫詳情 (Alias 'id')"
        },
        {
            "tool": "tej.company_info",
            "params": {"company_id": TEST_COID},
            "desc": "TEJ 基本資料 (Alias 'company_id')"
        },
        {
            "tool": "tej.stock_price",
            "params": {"ticker": TEST_COID, "opts.limit": 20}, # Limit 20 to test truncation (10 max)
            "desc": "TEJ 股價 (Alias 'ticker' + Truncation Test)"
        },
        {
            "tool": "searxng.search",
            "params": {"query": f"{TEST_NAME} 2025年營收"},
            "desc": "SearXNG (Alias 'query')"
        }
    ]

    # 3. Execution Loop
    print("\n[Step 2] 開始模擬 Agent 調用循環...")
    results_summary = []
    
    for case in test_cases:
        tool_name = case["tool"]
        params = case["params"]
        desc = case["desc"]
        
        print(f"\n🔹 [測試] {desc}")
        print(f"   調用: {tool_name} | 參數: {params}")
        
        try:
            # Simulate Worker execution
            start_t = asyncio.get_event_loop().time()
            # Note: invoke_tool is sync, but we wrap it to simulate async worker behavior if needed.
            # But tool_registry.invoke_tool is direct.
            result = tool_registry.invoke_tool(tool_name, params)
            end_t = asyncio.get_event_loop().time()
            
            duration = end_t - start_t
            
            # Validation
            status = "❌ 失敗"
            details = str(result)[:200]
            
            if isinstance(result, dict) and "error" in result:
                status = "❌ 錯誤"
                details = result["error"]
            elif isinstance(result, dict) and ("data" in result or "results" in result or "info" in result):
                # Check for empty data
                data = result.get("data") or result.get("results")
                if data is not None: # Empty list is valid result
                    status = "✅ 成功"
                else:
                    status = "⚠️ 空響應"
                    
                # Check warnings for truncation
                if result.get("warnings"):
                    details += f" [Warnings: {result['warnings']}]"
            else:
                 # Some tools return direct dicts without 'data' wrapper
                 if result:
                     status = "✅ 成功"
                 else:
                     status = "⚠️ 空響應"

            print(f"   結果: {status} ({duration:.4f}s)")
            print(f"   摘要: {details}...")
            
            results_summary.append({
                "tool": tool_name,
                "status": status,
                "details": details
            })
            
        except Exception as e:
            print(f"   🔥 異常: {e}")
            results_summary.append({"tool": tool_name, "status": "🔥 崩潰", "details": str(e)})

    # 4. Final Report
    print("\n" + "="*50)
    print("📊 測試總結報告")
    print("="*50)
    for res in results_summary:
        print(f"{res['status']} | {res['tool']:<30} | {res['details'][:50]}")
    
    print("\n測試結束。")

if __name__ == "__main__":
    asyncio.run(main())