import sys
import os

# Ensure current directory is in path for imports
sys.path.insert(0, os.getcwd())

from adapters.chinatimes_suite import ChinaTimesSearchAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter

def test_chinatimes(keyword):
    print(f"\n🔍 Testing ChinaTimes Search with: {keyword}")
    adapter = ChinaTimesSearchAdapter()
    try:
        # ChinaTimes Adapter needs "reason" param
        result = adapter.invoke({"keyword": keyword, "reason": "Verification"})
        citations = result.citations if hasattr(result, 'citations') else []
        
        if citations:
            print(f"✅ Found {len(citations)} results:")
            for item in citations[:3]:
                print(f"  - [{item.get('date', 'No Date')}] {item['title']} ({item['url']})")
        else:
            print("❌ No results found.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_duckduckgo(query):
    print(f"\n🔍 Testing DuckDuckGo with: {query}")
    try:
        adapter = DuckDuckGoAdapter()
        result = adapter.invoke({"q": query})
        
        citations = result.citations if hasattr(result, 'citations') else []
        if citations:
            print(f"✅ Found {len(citations)} results:")
            for item in citations[:3]:
                print(f"  - {item['title']} ({item['url']})")
                print(f"    Snippet: {item['snippet'][:100]}...")
        else:
            print("❌ No results found.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    keywords = [
        "群創 2025 新竹科學園區 優良廠商",
        "群創 創新產品獎 2025",
        "群創 3481 顯示器元件產品技術獎"
    ]
    
    for kw in keywords:
        test_chinatimes(kw)
        test_duckduckgo(kw)
