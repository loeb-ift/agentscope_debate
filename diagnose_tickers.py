import os
import sys
import logging
import json
from datetime import datetime, timedelta

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TickerDiagnosis")

# 確保可以導入模組
sys.path.append(os.getcwd())

from adapters.verified_price_adapter import VerifiedPriceAdapter
from adapters.tej_adapter import TEJStockPrice
from worker.utils.symbol_utils import normalize_symbol

def test_normalization():
    logger.info("=== 測試 normalize_symbol ===")
    test_cases = ["8069", "8069.TW", "8069.TWO", "TW:8069", "6924", "6924.TWO"]
    
    for symbol in test_cases:
        res = normalize_symbol(symbol)
        logger.info(f"Input: {symbol:<10} | Result: {res}")

def test_adapters():
    logger.info("\n=== 測試 Adapters (TEJ & VerifiedPrice) ===")
    
    # 測試標的：8069 (元太 - 上櫃公司)
    # 備選：6924 (榮惠-KY - 上櫃公司, 2024年上市可能較新)
    target_base = "8069" 
    variations = [target_base, f"{target_base}.TW", f"{target_base}.TWO"]
    
    # 設定日期：最近一個工作日 (或寫死一個已知有交易的日期)
    # 這裡使用 2024-01-05 (週五) 作為安全測試日期
    test_date = "2024-01-05" 
    start_date = "2024-01-01"
    end_date = "2024-01-05"

    tej_tool = TEJStockPrice()
    verified_tool = VerifiedPriceAdapter()

    for symbol in variations:
        logger.info(f"\n--- Testing Symbol: {symbol} ---")
        
        # 1. Test TEJ Direct
        try:
            logger.info(f"[TEJ] Invoking with {symbol}...")
            tej_res = tej_tool.invoke(coid=symbol, start_date=start_date, end_date=end_date)
            rows = tej_res.data.get("data", []) if hasattr(tej_res, 'data') else tej_res.get("data", {}).get("rows", [])
            
            # TEJ 回傳結構可能經過 normalize，也可能包在 ToolResult 中
            # ToolResult -> data -> rows
            if hasattr(tej_res, 'data') and isinstance(tej_res.data, dict):
                rows = tej_res.data.get("rows", [])
            
            success = len(rows) > 0
            logger.info(f"[TEJ] Result: {'SUCCESS' if success else 'EMPTY'} (Rows: {len(rows)})")
            if not success and hasattr(tej_res, 'raw'):
                 logger.info(f"[TEJ] Raw warnings: {tej_res.raw.get('meta', {}).get('warnings')}")

        except Exception as e:
            logger.error(f"[TEJ] Failed: {e}")

        # 2. Test Verified Price (Coordinator)
        try:
            logger.info(f"[Verified] Invoking with {symbol}...")
            # VerifiedPriceAdapter returns a dict directly from invoke (legacy style) or ToolResult?
            # Looking at code: invoke returns dict with "data" and "_meta"
            vp_res = verified_tool.invoke(symbol=symbol, date=test_date)
            
            data = vp_res.get("data", {})
            status = data.get("status")
            source = data.get("source")
            
            logger.info(f"[Verified] Status: {status}, Source: {source}")
            if status == "failed":
                logger.error(f"[Verified] Error: {data.get('error')}")
                
        except Exception as e:
            logger.error(f"[Verified] Failed: {e}")

if __name__ == "__main__":
    test_normalization()
    # 檢查是否有 API KEY，否則略過 Adapter 測試
    if not os.getenv("TEJ_API_KEY"):
        logger.warning("No TEJ_API_KEY found. TEJ direct tests will fail/skip, but testing VerifiedPrice (Yahoo Fallback)...")
    
    test_adapters()