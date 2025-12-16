"""
中時新聞網工具套件 (ChinaTimes Suite)

包含以下工具：
1. ChinaTimesSearchAdapter: 一般新聞搜尋
2. ChinaTimesStockRTAdapter: 個股即時行情
3. ChinaTimesStockNewsAdapter: 個股相關新聞
"""

from adapters.base import BaseToolAdapter, ToolResult
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import time
import logging

# 設定 logger
logger = logging.getLogger(__name__)

class ChinaTimesSearchAdapter(BaseToolAdapter):
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
        return "搜尋中時新聞網的新聞內容。僅接受單一實體名稱作為關鍵字 (如: '台積電', '賴清德')。"

    @property
    def auth_config(self) -> Dict:
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        return {
            "limit": 10,
            "period": 60
        }

    @property
    def cache_ttl(self) -> int:
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
                        "description": "搜尋關鍵字。必須是實體名稱 (Entity Name)，如 '台積電', '賴清德', 'iPhone'。"
                    },
                    "reason": {
                        "type": "string",
                        "description": "調用此工具的理由。說明為什麼需要這個事實支持。"
                    }
                },
                "required": ["keyword", "reason"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "keyword" not in params:
            raise ValueError("缺少必要參數: keyword")
        if "reason" not in params:
            raise ValueError("缺少必要參數: reason")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        keyword = params.get("keyword", "")
        return f"chinatimes_search:{hashlib.md5(keyword.encode()).hexdigest()}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes Search API Error: {http_status} - {body}")

    def invoke(self, params: Dict) -> ToolResult:
        self.validate(params)
        keyword = params["keyword"]
        reason = params["reason"]
        
        logger.info(f"搜尋中時新聞網: {keyword} (理由: {reason})")
        
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://es.chinatimes.com/search/content?Keyword={encoded_keyword}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.chinatimes.com/"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 嘗試解析 JSON，如果失敗則退回 HTML 解析 (為了相容性)
            try:
                data = response.json()
                results = self._parse_json(data)
                parse_method = "json"
            except ValueError:
                results = self._parse_html(response.text)
                parse_method = "html"
            
            citations = []
            for item in results:
                citations.append({
                    "source": "ChinaTimes",
                    "title": item["title"],
                    "url": item["url"],
                    "snippet": item["snippet"]
                })
            
            return ToolResult(
                data=results,
                raw={"response_snippet": response.text[:500], "count": len(results), "parse_method": parse_method},
                used_cache=False,
                cost=0.0,
                citations=citations
            )
            
        except Exception as e:
            logger.error(f"ChinaTimes search failed: {e}")
            return ToolResult(
                data=[],
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )

    def _parse_json(self, data: Dict) -> List[Dict]:
        """解析 JSON 格式的回應"""
        results = []
        
        # 預期結構: {"Total": 395, "Content": [...]}
        articles = data.get("Content", [])
        if not articles and isinstance(data, list):
            articles = data
            
        for article in articles[:10]:
            try:
                title = article.get("Title", "").strip()
                # 處理連結
                url = article.get("ArticleUrl", "")
                if url and not url.startswith("http"):
                    url = f"https://www.chinatimes.com{url}"
                
                # 處理日期
                date = article.get("PublishDatetime", "") or article.get("ArticleDate", "")
                
                # 處理摘要 (有些 API 可能沒有摘要欄位，用標題代替或留空)
                snippet = article.get("Description", "") or title
                
                results.append({
                    "title": title,
                    "url": url,
                    "date": date,
                    "snippet": snippet
                })
            except Exception:
                continue
                
        return results

    def _parse_html(self, html_content: str) -> List[Dict]:
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        
        article_list = soup.select('.article-list li')
        if not article_list:
            article_list = soup.select('.vertical-list li')
            
        if not article_list:
            # Fallback strategy
            headers = soup.find_all(['h3', 'h4'])
            for header in headers:
                link = header.find('a')
                if link and link.get('href'):
                    title = header.get_text(strip=True)
                    url = link.get('href')
                    if "chinatimes.com" in url or url.startswith("/"):
                        if not url.startswith("http"):
                             url = f"https://www.chinatimes.com{url}"
                        results.append({
                            "title": title,
                            "url": url,
                            "date": "",
                            "snippet": ""
                        })
            return results[:10]

        for item in article_list:
            try:
                title_tag = item.find(['h3', 'h4'])
                if not title_tag:
                    continue
                link = title_tag.find('a') or item.find('a')
                if not link:
                    continue
                    
                title = title_tag.get_text(strip=True)
                url = link.get('href')
                
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = "https://www.chinatimes.com" + url
                    
                date_tag = item.select_one('.date, .time, time')
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                snippet_tag = item.select_one('.intro, .desc, p')
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                results.append({
                    "title": title,
                    "url": url,
                    "date": date,
                    "snippet": snippet
                })
            except Exception:
                continue
                
        return results[:10]


class ChinaTimesStockRTAdapter(BaseToolAdapter):
    """
    中時財經 - 個股即時行情工具
    """

    @property
    def name(self) -> str:
        return "chinatimes.stock_rt"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "獲取個股即時行情 (中時)。支援上市/上櫃代碼 (e.g. 2330)。"

    @property
    def auth_config(self) -> Dict:
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        return {
            "limit": 60,
            "period": 60
        }

    @property
    def cache_ttl(self) -> int:
        return 60  # 即時行情快取 1 分鐘

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "股票代碼 (e.g. 2330)"
                    }
                },
                "required": ["code"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "code" not in params:
            raise ValueError("缺少必要參數: code")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        code = params.get("code", "")
        return f"chinatimes_stock_rt:{code}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes StockRT API Error: {http_status} - {body}")

    def invoke(self, params: Dict) -> ToolResult:
        self.validate(params)
        code = params["code"]
        
        url = f"https://wantrich.chinatimes.com/api/stock_rt/{code}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return ToolResult(
                data=data,
                raw=data,
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes Stock RT",
                    "title": f"Stock {code} Real-time Data",
                    "url": url,
                    "snippet": str(data)[:100]
                }]
            )
        except Exception as e:
            logger.error(f"ChinaTimes stock_rt failed: {e}")
            return ToolResult(
                data={},
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )


class ChinaTimesStockNewsAdapter(BaseToolAdapter):
    """
    中時財經 - 個股相關新聞工具
    """

    @property
    def name(self) -> str:
        return "chinatimes.stock_news"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "獲取個股相關新聞列表 (中時)。需提供代碼與名稱。"

    @property
    def auth_config(self) -> Dict:
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        return {
            "limit": 30,
            "period": 60
        }

    @property
    def cache_ttl(self) -> int:
        return 1800  # 新聞列表快取 30 分鐘

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "股票代碼 (e.g. 2330)"
                    },
                    "name": {
                        "type": "string",
                        "description": "股票中文名稱 (e.g. 台積電)"
                    },
                    "page": {
                        "type": "integer",
                        "description": "頁碼 (預設 1)",
                        "default": 1
                    }
                },
                "required": ["code", "name"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "code" not in params:
            raise ValueError("缺少必要參數: code")
        if "name" not in params:
            raise ValueError("缺少必要參數: name")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        code = params.get("code", "")
        page = params.get("page", 1)
        return f"chinatimes_stock_news:{code}:{page}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes StockNews API Error: {http_status} - {body}")

    def invoke(self, params: Dict) -> ToolResult:
        self.validate(params)
        code = params["code"]
        name = params["name"]
        page = params.get("page", 1)
        
        # URL 編碼名稱
        encoded_name = urllib.parse.quote(name)
        url = f"https://wantrich.chinatimes.com/api/search_stock_news/{code}/{encoded_name}/{page}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            citations = []
            
            # 處理不同的 API 回傳結構
            articles = []
            if isinstance(data, list):
                articles = data
            elif isinstance(data, dict):
                if "Content" in data: # 新的結構 (類似 Search API)
                    articles = data["Content"]
                elif "data" in data: # 舊的或備用結構
                    articles = data["data"]
            
            for item in articles[:5]:
                try:
                    title = item.get("Title", "")
                    
                    # 處理連結: 支援 Link (舊) 或 ArticleUrl (新)
                    link = item.get("Link", "") or item.get("ArticleUrl", "")
                    
                    if link and not link.startswith("http"):
                         # 判斷是 chinatimes.com 還是 wantrich
                         base_url = "https://wantrich.chinatimes.com"
                         if "chinatimes.com" in link:
                             # 如果已經包含 domain path 但沒 protocol (雖少見)
                             pass
                         elif link.startswith("/"):
                             # 預設為 wantrich，但如果是新聞搜尋 API 的結構，通常是指向主站
                             # 這裡做個簡單判斷，如果 item 有 ArticleUrl 通常是主站結構
                             if "ArticleUrl" in item:
                                 base_url = "https://www.chinatimes.com"
                             else:
                                 base_url = "https://wantrich.chinatimes.com"
                             
                             link = f"{base_url}{link}"

                    # 處理摘要: 支援 Intro (舊) 或 Description (新)
                    snippet = item.get("Intro", "") or item.get("Description", "")
                    
                    citations.append({
                        "source": "ChinaTimes Stock News",
                        "title": title,
                        "url": link,
                        "snippet": snippet
                    })
                except Exception:
                    continue

            return ToolResult(
                data=data,
                raw={"response_sample": str(data)[:500]},
                used_cache=False,
                cost=0.0,
                citations=citations
            )
        except Exception as e:
            logger.error(f"ChinaTimes stock_news failed: {e}")
            return ToolResult(
                data=[],
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )