import logging
from adapters.chinatimes_suite import ChinaTimesSearchAdapter

# 設定 logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chinatimes_search_missing_reason():
    """測試在缺少 reason 參數的情況下調用 ChinaTimesSearchAdapter"""
    
    adapter = ChinaTimesSearchAdapter()
    
    # 測試參數：只有 keyword，缺少 reason
    params = {
        "keyword": "台積電"
    }
    
    logger.info(f"測試參數: {params}")
    
    try:
        # 1. 測試 validate 方法
        logger.info("正在執行 validate()...")
        adapter.validate(params)
        logger.info("validate() 通過")
        
        # 2. 測試 invoke 方法
        logger.info("正在執行 invoke()...")
        result = adapter.invoke(**params)
        
        if result.data:
            logger.info("invoke() 成功，收到資料:")
            logger.info(f"搜尋結果數量: {len(result.data)}")
            logger.info(f"第一筆標題: {result.data[0].get('title', 'N/A')}")
        else:
            logger.warning("invoke() 成功，但未收到資料")
            
    except Exception as e:
        logger.error(f"測試失敗: {e}")
        raise

if __name__ == "__main__":
    test_chinatimes_search_missing_reason()