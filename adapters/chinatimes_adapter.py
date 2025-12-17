from adapters.base import BaseToolAdapter, ToolResult
from typing import Dict, Any, List
import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import time
import logging

# 設定 logger
logger = logging.getLogger(__name__)

class ChinaTimesAdapter(BaseToolAdapter):
    """
    中時新聞網搜尋工具轉接器。
    用於搜尋中時新聞網 (chinatimes.com) 的新聞內容。
    """

    @property
    def name(self) -> str:
        return "news.search_chinatimes"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "搜尋中時新聞網 (ChinaTimes) 新聞內容。支援以實體名稱 (如 '台積電', '賴清德') 查找相關報導。"

    @property
    def auth_config(self) -> Dict:
        # 不需要特殊驗證
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        # 建議的速率限制
        return {
            "limit": 10,
            "period": 60
        }

    @property
    def cache_ttl(self) -> int:
        # 搜尋結果快取 1 小時
        return 3600

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜尋關鍵字 (必填)。僅支援單一實體名稱 (Entity Name)，例如 '台積電', '鴻海', 'AI伺服器'。"
                    },
                    "reason": {
                        "type": "string",
                        "description": "調用理由 (必填)。請說明為何需要查詢此新聞資訊，以利後續審計。"
                    }
                },
                "required": ["keyword", "reason"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "keyword" not in params:
            raise ValueError("Missing required parameter: keyword")
        if "reason" not in params:
            raise ValueError("Missing required parameter: reason")

    def auth(self, req: Dict) -> Dict:
        # 不需要額外驗證標頭
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        # 根據關鍵字建立快取鍵
        keyword = params.get("keyword", "")
        return f"chinatimes:{hashlib.md5(keyword.encode()).hexdigest()}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes API Error: {http_status} - {body}")

    def invoke(self, params: Dict) -> ToolResult:
        self.validate(params)
        keyword = params["keyword"]
        reason = params["reason"]
        
        logger.info(f"Searching ChinaTimes for: {keyword} (Reason: {reason})")
        
        # 構建 URL (注意: 中時搜尋只接受 URL encoded 的關鍵字)
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://es.chinatimes.com/search/content?Keyword={encoded_keyword}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.chinatimes.com/"
        }
        
        start_time = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析 HTML
            results = self._parse_html(response.text)
            
            # 準備回傳結果
            normalized_data = []
            citations = []
            
            for item in results:
                normalized_data.append(item)
                citations.append({
                    "source": "ChinaTimes",
                    "title": item["title"],
                    "url": item["url"],
                    "snippet": item["snippet"]
                })
            
            cost = 0.0 # 此工具無 API 成本
            
            return ToolResult(
                data=normalized_data,
                raw={"html_snippet": response.text[:500], "count": len(results)},
                used_cache=False,
                cost=cost,
                citations=citations
            )
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch ChinaTimes: {e}")
            return ToolResult(
                data=[],
                raw={"error": str(e)},
                used_cache=False,
                cost=0,
                citations=[]
            )
        except Exception as e:
            logger.error(f"Error parsing ChinaTimes results: {e}")
            return ToolResult(
                data=[],
                raw={"error": f"Parsing Error: {str(e)}"},
                used_cache=False,
                cost=0,
                citations=[]
            )

    def _parse_html(self, html_content: str) -> List[Dict]:
        """
        解析中時新聞網的搜尋結果 HTML
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        
        # 策略 1: 尋找 .article-list 區塊 (常見結構)
        article_list = soup.select('.article-list li')
        
        # 策略 2: 如果找不到 .article-list，尋找一般的列表結構
        if not article_list:
            article_list = soup.select('.vertical-list li')
            
        # 策略 3: 如果還是找不到，嘗試抓取所有標題 (h3, h4) 並過濾
        if not article_list:
            headers = soup.find_all(['h3', 'h4'])
            for header in headers:
                link = header.find('a')
                if link and link.get('href'):
                    title = header.get_text(strip=True)
                    url = link.get('href')
                    # 嘗試找尋鄰近的描述文字
                    container = header.find_parent()
                    snippet = ""
                    if container:
                        p_tag = container.find('p')
                        if p_tag:
                            snippet = p_tag.get_text(strip=True)
                    
                    # 確保是新聞連結
                    if "chinatimes.com" in url or url.startswith("/"):
                        if not url.startswith("http"):
                             url = f"https://www.chinatimes.com{url}"
                             
                        results.append({
                            "title": title,
                            "url": url,
                            "date": "", # 難以從通用結構取得
                            "snippet": snippet
                        })
            return results[:10] # 限制返回數量

        # 解析列表項目 (策略 1 & 2)
        for item in article_list:
            try:
                title_tag = item.find(['h3', 'h4'])
                if not title_tag:
                    continue
                    
                link = title_tag.find('a')
                if not link:
                    link = item.find('a')
                    
                if not link:
                    continue
                    
                title = title_tag.get_text(strip=True)
                url = link.get('href')
                
                # 補全 URL
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = "https://www.chinatimes.com" + url
                    
                # 提取日期
                date_tag = item.select_one('.date, .time, time')
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                # 提取摘要
                snippet_tag = item.select_one('.intro, .desc, p')
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                results.append({
                    "title": title,
                    "url": url,
                    "date": date,
                    "snippet": snippet
                })
            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue
                
        return results[:10]
