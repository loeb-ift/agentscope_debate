import sys
import os
import asyncio
from datetime import datetime

# 確保可以導入 worker 模組
sys.path.append(os.getcwd())

from worker.utils.price_proof_coordinator import PriceProofCoordinator

async def verify_otc_price():
    """
    驗證 OTC 股票 (元太 8069) 的價格檢索邏輯
    預期: 
    1. 識別為 OTC 股票
    2. 跳過 TWSE 查詢 (因為 TWSE 只支援上市)
    3. 成功使用 Yahoo Finance 作為 Fallback
    """
    print("\n=== 開始驗證 OTC 價格檢索邏輯 ===\n")
    
    coordinator = PriceProofCoordinator()
    
    # 測試案例: 8069 (元太) - 已知上櫃股票 (OTC)
    # 注意: 我們傳入 "8069.TWO" 來明確指定，但也測試代碼是否能處理它
    symbol = "8069.TWO" 
    
    print(f"正在查詢股票: {symbol} (預期為 OTC/上櫃)")
    
    try:
        # 執行價格查詢 (直接調用 async 方法以避免 event loop 衝突)
        result = await coordinator.get_verified_price_async(symbol)
        
        print(f"\n查詢結果: {result}")
        
        # 驗證檢查點
        checks = []
        
        # 1. 檢查狀態
        status_ok = result.get('status') == 'success'
        checks.append(("狀態為 success", status_ok, result.get('status')))
        
        # 2. 檢查來源 (應為 Yahoo)
        source = result.get('source', '')
        source_ok = 'Yahoo' in source
        checks.append(("來源包含 Yahoo", source_ok, source))
        
        # 3. 檢查代號 (應正規化為 8069)
        res_symbol = result.get('symbol', '')
        symbol_ok = '8069' in res_symbol
        checks.append(("代號正確", symbol_ok, res_symbol))
        
        # 4. 檢查是否有價格
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
            print("\n✅ 測試成功: OTC 股票正確跳過 TWSE 並使用 Yahoo Fallback")
        else:
            print("\n❌ 測試失敗: 未滿足所有預期條件")
            
    except Exception as e:
        print(f"\n❌ 發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_otc_price())