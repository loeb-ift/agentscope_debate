import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from api.tool_registry import tool_registry

async def verify_tsmc_integration():
    print("=== 驗證台積電 (TSMC) 數據整合 ===")
    
    symbol = "2330.TW"
    
    # 1. 驗證 pandas-datareader (financial.pdr_reader)
    print("\n[1/2] 正在驗證 pandas-datareader (Stooq 來源)...")
    pdr_params = {
        "symbol": symbol,
        "start_date": "2024-11-19",
        "end_date": "2025-12-19",
        "source": "stooq"
    }
    
    pdr_result = tool_registry.invoke_tool("financial.pdr_reader", pdr_params)
    
    if pdr_result.get("success"):
        print(f"✓ PDR 成功獲取數據，筆數: {pdr_result.get('count')}")
        if pdr_result.get('data'):
            latest = pdr_result.get('data')[0]
            print(f"  最新數據日期: {latest.get('date')}, 收盤價: {latest.get('close')}")
    else:
        print(f"✗ PDR 獲取失敗 (Stooq 可能無此資料): {pdr_result.get('error')}")
        print("  註：Stooq 對台股支援有限，若失敗將依賴 EDA 流程中的降級機制。")

    # 2. 驗證 pandas-ta-classic (financial.technical_analysis)
    print("\n[2/2] 正在驗證 pandas-ta-classic 技術指標分析 (Yahoo 來源)...")
    ta_params = {
        "symbol": symbol,
        "lookback_days": 120,
        "indicators": ["sma", "rsi", "macd", "bbands"]
    }
    
    ta_result = tool_registry.invoke_tool("financial.technical_analysis", ta_params)
    
    if ta_result.get("success"):
        print("✓ 技術分析工具成功產生結果：")
        print(f"  代碼: {ta_result.get('symbol')}")
        print(f"  信號摘要: \n{ta_result.get('summary')}")
        print(f"  最新指標值: {ta_result.get('latest_values')}")
    else:
        print(f"✗ 技術分析工具失敗: {ta_result.get('error')}")

if __name__ == "__main__":
    asyncio.run(verify_tsmc_integration())
