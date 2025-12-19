import os
import sys
import json
from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 確保可以導入專案模組
sys.path.append(os.getcwd())

from adapters.database_tool_adapter import SearchCompany
from adapters.tej_adapter import TEJMonthlyRevenue, TEJCompanyInfo

def print_result(tool_name, result):
    print(f"\n{'='*20} {tool_name} {'='*20}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("="*50)

def main():
    print("開始驗證 6924 (榮惠-KY) 數據真實性...\n")

    # 1. 驗證 internal.search_company
    print("1. 調用 internal.search_company 搜尋 '6924'...")
    search_tool = SearchCompany()
    try:
        search_result = search_tool.invoke(keyword="6924")
        print_result("internal.search_company", search_result)
        
        # 獲取公司 ID
        company_id = "6924.TW" # 預設值
        if "results" in search_result and search_result["results"]:
            company_id = search_result["results"][0].get("id", "6924.TW")
            print(f"-> 檢測到公司 ID: {company_id}")
        else:
            print(f"-> 未檢測到公司，將嘗試使用預設 ID: {company_id}")

    except Exception as e:
        print(f"ERROR calling search_company: {e}")
        company_id = "6924.TW"

    # 2. 驗證 tej.company_info
    print(f"\n2. 調用 tej.company_info 確認公司基本資料 (ID: {company_id})...")
    info_tool = TEJCompanyInfo()
    try:
        info_result = info_tool.invoke(coid=company_id)
        print_result("tej.company_info", info_result)
    except Exception as e:
        print(f"ERROR calling tej.company_info: {e}")

    # 3. 驗證 tej.monthly_revenue (2024-2025)
    print(f"\n3. 調用 tej.monthly_revenue 查詢營收 (ID: {company_id}, Range: 2024-01-01 ~ 2025-12-31)...")
    revenue_tool = TEJMonthlyRevenue()
    try:
        revenue_result = revenue_tool.invoke(
            coid=company_id,
            start_date="2024-01-01",
            end_date="2025-12-31",
            limit=100
        )
        print_result("tej.monthly_revenue", revenue_result)
        
        # 分析結果
        rows = revenue_result.get("data", {}).get("rows", [])
        print(f"\n分析: 共獲取 {len(rows)} 筆營收資料")
        if rows:
            dates = [row.get("mdate") for row in rows]
            print(f"數據涵蓋月份: {dates}")
            
            has_future_data = any("2025" in str(d) for d in dates)
            if has_future_data:
                print("⚠️ 警告: 發現 2025 年以後的數據！")
            else:
                print("✅ 正常: 未發現 2025 年以後的未來數據。")
        else:
            print("ℹ️ 提示: 未獲取到任何營收數據 (可能是空列表)。")

    except Exception as e:
        print(f"ERROR calling tej.monthly_revenue: {e}")

if __name__ == "__main__":
    main()