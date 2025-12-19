import logging
import json
import sys
from typing import Dict, Any

# 設定 logging 顯示 INFO 等級訊息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 嘗試導入中時工具套件
try:
    from adapters.chinatimes_suite import (
        ChinaTimesSearchAdapter,
        ChinaTimesStockRTAdapter,
        ChinaTimesStockNewsAdapter,
        ChinaTimesStockKlineAdapter
    )
    print("✅ 成功導入 ChinaTimes Suite Adapters")
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    sys.exit(1)

def print_result(tool_name: str, result: Any):
    """美化輸出工具結果"""
    print(f"\n{'='*20} {tool_name} Result {'='*20}")
    
    if hasattr(result, 'to_dict'):
        data = result.to_dict()
    else:
        data = str(result)
        
    # 簡化輸出，避免過多雜訊
    if isinstance(data, dict):
        # 處理 citations
        citations = data.get('citations', [])
        if citations:
            print(f"\n📚 Citations ({len(citations)}):")
            for i, cite in enumerate(citations, 1):
                print(f"  {i}. [{cite.get('source', 'Unknown')}] {cite.get('title', 'No Title')}")
                print(f"     URL: {cite.get('url', 'N/A')}")
                snippet = cite.get('snippet', '')
                if snippet:
                    print(f"     Snippet: {snippet[:100]}...")
        
        # 處理 raw data (如果有的話，且不是太長)
        raw = data.get('data', [])
        if raw and isinstance(raw, list) and len(raw) > 0:
             print(f"\n🔢 Data Items Found: {len(raw)}")
        elif raw and isinstance(raw, dict):
             print(f"\n🔢 Data Keys: {list(raw.keys())}")

        # 顯示原始回應的片段以供除錯
        if 'raw' in data and data['raw']:
             print(f"\n🔍 Raw Response Preview: {str(data['raw'])[:200]}...")

    else:
        print(data)
    print("="*60 + "\n")

def test_chinatimes_search():
    """測試一般新聞搜尋"""
    print("\n🔍 Testing ChinaTimesSearchAdapter...")
    adapter = ChinaTimesSearchAdapter()
    
    # 測試案例: 搜尋 "台積電"
    params = {
        "keyword": "台積電",
        "reason": "驗證搜尋功能是否正常運作"
    }
    
    try:
        print(f"👉 Invoking with params: {params}")
        result = adapter.invoke(**params)
        print_result("ChinaTimes Search", result)
    except Exception as e:
        print(f"❌ Search failed: {e}")

def test_chinatimes_stock_rt():
    """測試個股即時行情"""
    print("\n📈 Testing ChinaTimesStockRTAdapter...")
    adapter = ChinaTimesStockRTAdapter()
    
    # 測試案例: 查詢 "2330" (台積電)
    params = {
        "code": "2330"
    }
    
    try:
        print(f"👉 Invoking with params: {params}")
        result = adapter.invoke(**params)
        print_result("ChinaTimes Stock RT", result)
    except Exception as e:
        print(f"❌ Stock RT failed: {e}")

def test_chinatimes_stock_news():
    """測試個股新聞"""
    print("\n📰 Testing ChinaTimesStockNewsAdapter...")
    adapter = ChinaTimesStockNewsAdapter()
    
    # 測試案例: 查詢 "2330" (台積電)
    params = {
        "code": "2330",
        "name": "台積電"
    }
    
    try:
        print(f"👉 Invoking with params: {params}")
        result = adapter.invoke(**params)
        print_result("ChinaTimes Stock News", result)
    except Exception as e:
        print(f"❌ Stock News failed: {e}")

def test_chinatimes_stock_kline():
    """測試個股K線"""
    print("\n📊 Testing ChinaTimesStockKlineAdapter...")
    adapter = ChinaTimesStockKlineAdapter()
    
    # 測試案例: 查詢 "2330" (台積電) 日K
    params = {
        "code": "2330",
        "type": "k1"
    }
    
    try:
        print(f"👉 Invoking with params: {params}")
        result = adapter.invoke(**params)
        print_result("ChinaTimes Stock Kline", result)
    except Exception as e:
        print(f"❌ Stock Kline failed: {e}")

def test_chinatimes_alias():
    """測試參數別名自動映射"""
    print("\n🔄 Testing ChinaTimesStockRTAdapter with alias 'ticker'...")
    adapter = ChinaTimesStockRTAdapter()
    
    # 測試案例: 使用 'ticker' 代替 'code'
    params = {
        "ticker": "2330"
    }
    
    try:
        print(f"👉 Invoking with params: {params}")
        # Use **kwargs style invocation as Registry does
        result = adapter.invoke(**params)
        print_result("ChinaTimes Stock RT (Alias)", result)
    except Exception as e:
        print(f"❌ Stock RT Alias test failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting ChinaTimes Suite Verification")
    
    # Run standard tests (updated to use **kwargs)
    test_chinatimes_search()
    test_chinatimes_stock_rt()
    
    # Run alias test
    test_chinatimes_alias()
    
    print("🏁 Verification Complete")