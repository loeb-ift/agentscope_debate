
import sys
import os
import asyncio
from datetime import datetime

# 確保可以導入 worker 模組
sys.path.append(os.getcwd())

from worker.utils.price_proof_coordinator import PriceProofCoordinator

async def verify_av_integration():
    """
    驗證 Alpha Vantage 整合進 PriceProofCoordinator
    測試對象: TSM (US Stock)
    預期路徑:
    1. TEJ (查無 TSM or 空) -> Fail
    2. TWSE (TSM 非台股) -> Fail or Skip
    3. Alpha Vantage -> Success
    """
    print("\n=== 驗證 Alpha Vantage Integration ===\n")
    
    coordinator = PriceProofCoordinator()
    
    # 測試對象: TSM (US)
    # TSM 在 normalize_symbol 中應該會被判定為 market='US' (預設)
    symbol = "TSM" 
    
    print(f"正在查詢股票: {symbol} (預期觸發 Alpha Vantage)")
    
    try:
        # 使用 async wrapper
        result = await coordinator.get_verified_price_async(symbol)
        
        print(f"\n查詢結果: {result}")
        
        # 驗證檢查點
        checks = []
        
        # 1. 檢查狀態
        status_ok = result.get('status') == 'success'
        checks.append(("狀態為 success", status_ok, result.get('status')))
        
        # 2. 檢查來源 (應為 Alpha Vantage)
        source = result.get('source', '')
        source_ok = 'Alpha Vantage' in source
        checks.append(("來源包含 Alpha Vantage", source_ok, source))
        
        # 3. 檢查是否有價格
        price = result.get('price')
        price_ok = price is not None and price > 0
        checks.append(("價格有效", price_ok, price))
        
        # 輸出驗證結果
        print("\n=== 驗證報告 ===")
        all_passed = True
        for desc, passed, value in checks:
            status_icon = "✅" if passed else "❌"
            print(f"{status_icon} {desc}: {value}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n✅ 測試成功: 正確使用 Alpha Vantage 獲取 US 股票數據")
        else:
            print("\n❌ 測試失敗")
            
    except Exception as e:
        print(f"\n❌ 發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_av_integration())
