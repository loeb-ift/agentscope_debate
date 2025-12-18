
import asyncio
import sys
import os
from datetime import datetime

# Set up path to import modules
sys.path.insert(0, '/app')

# 模擬環境變數
if not os.environ.get("REDIS_HOST"):
    os.environ["REDIS_HOST"] = "redis"

async def test_ods_eda_direct():
    """
    測試直接調用 ODS Internal Adapter
    """
    print("=" * 80)
    print("🔍 ODS Internal EDA Tool 驗證")
    print("=" * 80)
    
    try:
        from adapters.ods_internal_adapter import ODSInternalAdapter
        adapter = ODSInternalAdapter()
        print(f"✓ Adapter Name: {adapter.name}")
    except ImportError as e:
        print(f"❌ Adapter Import Failed: {e}")
        return

    # 準備測試 CSV 路徑 (需要是容器內的絕對路徑)
    # 假設我們掛載了 /data 到容器內的 /data
    csv_path = "/data/staging/scenario_test_2330/2330.TW.csv"
    
    # 本地測試時，如果沒有在 docker 內，可能需要調整路徑
    if not os.path.exists(csv_path) and os.path.exists("data/staging/scenario_test_2330/2330.TW.csv"):
        # 本地路徑轉換為絕對路徑
        csv_path = os.path.abspath("data/staging/scenario_test_2330/2330.TW.csv")
    
    print(f"📂 測試 CSV: {csv_path}")
    if not os.path.exists(csv_path):
        print("❌ CSV 檔案不存在，無法測試")
        return

    params = {
        "csv_path": csv_path,
        "include_cols": ["Open", "High", "Low", "Close", "Volume"],
        "sample": 5000,
        "lang": "zh"
    }
    
    print("📊 執行參數:", params)
    print("⏳ 調用 ODS EDA 服務 (模擬)...")
    
    # 由於我們沒有真的 ODS 服務在運行 (http://localhost:8000/api/eda/describe)，
    # 這裡的調用預期會失敗 (Connection Refused)。
    # 但我們要驗證的是 Adapter 的邏輯是否正確處理錯誤。
    
    result = adapter.invoke(**params)
    
    print("📋 結果:")
    print(result)
    
    if result.get("success"):
        print("✅ 調用成功")
    else:
        print("⚠️ 調用失敗 (預期中，若無後端服務)")
        print(f"  錯誤: {result.get('error')}")

async def test_chairman_eda_tsmc():
    """
    測試主席使用 EDA 工具分析台積電
    """
    print("\n" + "=" * 80)
    print("🔍 主席 EDA Tool 驗證 - 台積電分析")
    print("=" * 80)
    
    try:
        from adapters.eda_tool_adapter import EDAToolAdapter
        adapter = EDAToolAdapter()
        print(f"✓ Adapter Name: {adapter.name}")
    except ImportError as e:
        print(f"❌ Adapter Import Failed: {e}")
        return

    test_params = {
        "symbol": "2330.TW",
        "debate_id": "tsmc_test_001",
        "lookback_days": 30,
        "include_financials": False # 簡化測試
    }
    
    print("📊 執行參數:", test_params)
    print("⏳ 調用 Chairman EDA Tool...")
    
    # 這裡會嘗試拉取數據 -> 調用 ODS -> 生成報告
    # 如果 ODS 服務不通，這步也會失敗，但會經過降級處理或報錯
    
    try:
        # 為了避免真實拉取數據等待過久，我們可以 mock _invoke_async 中的部分邏輯
        # 但這裡是集成測試，盡量跑真實流程。
        # 不過如果沒有網絡，拉取數據會失敗。
        
        result = await adapter._invoke_async(**test_params)
        
        print("📋 結果:")
        if result.get("success"):
            print("✅ 流程成功")
            print(f"  摘要: {result.get('summary')[:100]}...")
            if result.get("degraded"):
                print("  ⚠️ 降級模式")
        else:
            print("❌ 流程失敗")
            print(f"  錯誤: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 執行異常: {e}")

def main():
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    asyncio.run(test_ods_eda_direct())
    asyncio.run(test_chairman_eda_tsmc())

if __name__ == "__main__":
    main()
