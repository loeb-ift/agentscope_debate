import sys
import os
import json
from dotenv import load_dotenv
from worker.dynamic_tool_loader import DynamicToolLoader
from api.tool_registry import tool_registry
from adapters.tej_adapter import TEJCompanyInfo, TEJStockPrice

# 載入 .env
load_dotenv()

def verify_comparison():
    print("⚖️  開始執行 TEJ 新舊架構對比驗證...")
    
    tej_key = os.getenv("TEJ_API_KEY")
    if not tej_key:
        print("❌ TEJ_API_KEY 未設定，無法執行真實 API 對比。")
        return

    # 1. 準備舊版工具 (Legacy)
    print("\n[1] 初始化舊版工具 (Legacy Adapter)...")
    legacy_company = TEJCompanyInfo(api_key=tej_key)
    legacy_price = TEJStockPrice(api_key=tej_key)
    print("✅ 舊版工具初始化完成。")

    # 2. 準備新版工具 (OpenAPI)
    print("\n[2] 載入新版工具 (OpenAPI Adapter)...")
    count = DynamicToolLoader.load_all_tools(tool_registry)
    if count == 0:
        print("❌ 無法載入新版工具。")
        return
    
    # 獲取新版 adapter instance
    try:
        new_company = tool_registry.get_tool_data("tej.company_info")["instance"]
        new_price = tool_registry.get_tool_data("tej.stock_price")["instance"]
        print("✅ 新版工具載入完成。")
    except Exception as e:
        print(f"❌ 獲取新版工具失敗: {e}")
        return

    # 3. 執行對比測試 - 公司基本資料
    print("\n------------------------------------------------")
    print("🧪 測試案例 A: 公司基本資料 (2330 台積電)")
    print("------------------------------------------------")
    
    try:
        # 舊版調用
        print("   🔸 呼叫舊版工具...")
        res_legacy = legacy_company.invoke(coid="2330", limit=1)
        data_legacy = res_legacy.data.get("rows", [])
        # 若 legacy adapter 未將 datatable.data 映射到 rows，則從 raw 補取
        if not data_legacy and isinstance(getattr(res_legacy, 'raw', None), dict):
            data_legacy = res_legacy.raw.get("datatable", {}).get("data", [])
        
        # 新版調用 (注意參數差異: limit -> opts.limit)
        print("   🔹 呼叫新版工具...")
        res_new_raw = new_company.invoke(**{"coid": "2330", "opts.limit": 1})
        
        # 新版回傳可能是 { data: [...] } 或 { datatable: { data: [...] } }
        dt = res_new_raw.get("data")
        if isinstance(dt, list):
            data_new = dt
        else:
            data_new = res_new_raw.get("datatable", {}).get("data", [])

        # 比較
        print(f"   📊 結果比較: 舊版 {len(data_legacy)} 筆 vs 新版 {len(data_new)} 筆")
        
        if len(data_legacy) != len(data_new):
             print("   ❌ 筆數不一致！")
        else:
             # 深度比較第一筆資料 (忽略可能的 metadata 差異)
             if len(data_legacy) > 0:
                 row_old = data_legacy[0]
                 row_new = data_new[0]
                 
                 # 簡單比較 key 集合
                 keys_old = set(row_old.keys())
                 keys_new = set(row_new.keys())
                 
                 if keys_old == keys_new:
                     print("   ✅ 欄位結構完全一致")
                 else:
                     print(f"   ⚠️ 欄位結構差異: {keys_old ^ keys_new}")

                 # 比較值 (取前5個欄位抽樣)
                 sample_keys = list(keys_old)[:5]
                 match = True
                 for k in sample_keys:
                     if str(row_old.get(k)) != str(row_new.get(k)):
                         print(f"   ❌ 值不匹配: Key={k}, Old={row_old.get(k)}, New={row_new.get(k)}")
                         match = False
                 if match:
                     print("   ✅ 抽樣數據內容一致")
             else:
                 print("   ⚠️ 兩者皆無資料回傳 (可能是權限或參數問題，但行為一致)")

    except Exception as e:
        print(f"   ❌ 測試 A 發生例外: {e}")


    # 4. 執行對比測試 - 股價資料
    print("\n------------------------------------------------")
    print("🧪 測試案例 B: 股價資料 (2330, 2024-01-01 ~ 2024-01-05)")
    print("------------------------------------------------")
    
    try:
        params_legacy = {"coid": "2330", "start_date": "2024-01-01", "end_date": "2024-01-05", "limit": 5}
        params_new = {"coid": "2330", "mdate.gte": "2024-01-01", "mdate.lte": "2024-01-05", "opts.limit": 5}

        # 舊版調用
        print("   🔸 呼叫舊版工具...")
        res_legacy = legacy_price.invoke(**params_legacy)
        data_legacy = res_legacy.data.get("rows", [])
        if not data_legacy and isinstance(getattr(res_legacy, 'raw', None), dict):
            data_legacy = res_legacy.raw.get("datatable", {}).get("data", [])
        
        # 新版調用
        print("   🔹 呼叫新版工具...")
        res_new_raw = new_price.invoke(**params_new)
        dt = res_new_raw.get("data")
        if isinstance(dt, list):
            data_new = dt
        else:
            data_new = res_new_raw.get("datatable", {}).get("data", [])

        # 比較
        print(f"   📊 結果比較: 舊版 {len(data_legacy)} 筆 vs 新版 {len(data_new)} 筆")
        
        if len(data_legacy) != len(data_new):
             print("   ❌ 筆數不一致！")
             print(f"Old: {data_legacy}")
             print(f"New: {data_new}")
        else:
             if len(data_legacy) > 0:
                 # 比較第一筆
                 if data_legacy[0] == data_new[0]:
                     print("   ✅ 資料內容完全一致 (Full Match)")
                 else:
                     print("   ⚠️ 資料內容有差異 (可能是排序或格式)")
                     print(f"Old[0]: {data_legacy[0]}")
                     print(f"New[0]: {data_new[0]}")
             else:
                 print("   ⚠️ 兩者皆無資料回傳")

    except Exception as e:
        print(f"   ❌ 測試 B 發生例外: {e}")

    print("\n🏁 對比驗證結束")

if __name__ == "__main__":
    verify_comparison()