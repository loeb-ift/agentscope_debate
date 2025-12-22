import requests
from bs4 import BeautifulSoup
import urllib.parse

def probe(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://es.chinatimes.com/search/content?Keyword={encoded_keyword}"
    print(f"Probing: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 嘗試找出文章列表容器
        # 常見的中時結構可能有 .article-list, .list-right, 或者是特定的 ul/li 結構
        
        # 尋找包含標題的元素，通常是 h3 或 h4
        titles = soup.find_all(['h3', 'h4'])
        print(f"Found {len(titles)} potential title elements")
        
        for i, title in enumerate(titles[:5]):
            print(f"--- Title {i} ---")
            print(title.prettify())
            parent = title.find_parent()
            if parent:
                print(f"Parent class: {parent.get('class')}")
                
        # 嘗試尋找新聞列表區塊
        article_list = soup.select('.article-list')
        if article_list:
            print(f"\nFound .article-list: {len(article_list)} items")
            for item in article_list[:2]:
                print(item.prettify()[:500])
        
        # 嘗試其他可能的 class
        candidates = ['.list-right', '.search-result-list', 'ul.vertical-list', '.vertical-list']
        for c in candidates:
            found = soup.select(c)
            if found:
                print(f"\nFound {c}: {len(found)} items")
                for item in found[:1]:
                    print(item.prettify()[:200])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    probe("台積電")