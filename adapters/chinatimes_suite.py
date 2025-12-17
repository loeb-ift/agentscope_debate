"""
中時新聞網工具套件 (ChinaTimes Suite)

包含以下工具：
1. ChinaTimesSearchAdapter: 一般新聞搜尋
2. ChinaTimesStockRTAdapter: 個股即時行情
3. ChinaTimesStockNewsAdapter: 個股相關新聞
4. ChinaTimesStockKlineAdapter: 個股日K線
5. ChinaTimesMarketIndexAdapter: 大盤指數
6. ChinaTimesMarketRankingsAdapter: 市場排行
7. ChinaTimesSectorAdapter: 類股分析
8. ChinaTimesStockFundamentalAdapter: 個股健診
9. ChinaTimesBalanceSheetAdapter: 資產負債表 (New)
10. ChinaTimesIncomeStatementAdapter: 損益表 (New)
11. ChinaTimesCashFlowAdapter: 現金流量表 (New)
12. ChinaTimesFinancialRatiosAdapter: 財務比率 (New)
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
        return "搜尋中時新聞網 (ChinaTimes) 新聞內容。支援以實體名稱 (如 '台積電', '賴清德') 查找相關報導。"

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
                "required": ["keyword"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "keyword" not in params:
            raise ValueError("缺少必要參數: keyword")
        # reason 非強制，若無則在 invoke 中使用預設值

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        keyword = params.get("keyword", "")
        return f"chinatimes_search:{hashlib.md5(keyword.encode()).hexdigest()}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes Search API Error: {http_status} - {body}")

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        keyword = params["keyword"]
        reason = params.get("reason", "No reason provided")
        
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
        return "獲取台股個股即時行情 (ChinaTimes)。支援上市與上櫃股票代碼 (如 2330)。"

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
        # Auto-correct aliases
        if "code" not in params:
            for alias in ["symbol", "ticker", "id", "coid", "stock_id"]:
                if alias in params:
                    params["code"] = params[alias]
                    break
        
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

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
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


class ChinaTimesStockKlineAdapter(BaseToolAdapter):
    """
    中時財經 - 個股K線數據工具 (日K)
    """

    @property
    def name(self) -> str:
        return "chinatimes.stock_kline"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "獲取台股個股日 K 線歷史數據。支援上市與上櫃股票代碼。回傳包含日期、開盤、最高、最低、收盤價與成交量。"

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
        return 3600  # K線數據快取 1 小時

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
                    "type": {
                        "type": "string",
                        "description": "K線類型 (預設 k1=日K)",
                        "default": "k1",
                        "enum": ["k1"]
                    }
                },
                "required": ["code"]
            }
        }

    def validate(self, params: Dict) -> None:
        # Auto-correct aliases
        if "code" not in params:
            for alias in ["symbol", "ticker", "id", "coid", "stock_id"]:
                if alias in params:
                    params["code"] = params[alias]
                    break
                    
        if "code" not in params:
            raise ValueError("缺少必要參數: code")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        code = params.get("code", "")
        type_val = params.get("type", "k1")
        return f"chinatimes_stock_kline:{code}:{type_val}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes StockKline API Error: {http_status} - {body}")

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        k_type = params.get("type", "k1")
        
        # 判斷上市或上櫃 (簡單規則：3碼或4碼通常是上市，但中時API似乎需要區分 stk_tw (上市) 或其他？
        # 根據探測結果，URL 是 /api/stock/stk_tw/{code}/k1
        # 但如果是上櫃 (OTC)，可能是 /api/stock/stk_otc/{code}/k1 ?
        # 暫時先假設 stk_tw 通用，或者嘗試這兩個路徑。
        # 中時 API 對上市上櫃的區分：上市=stk_tw, 上櫃=stk_os ? 不確定。
        # 讓我們使用一個通用邏輯：先試 stk_tw。
        
        url_tw = f"https://wantrich.chinatimes.com/api/stock/stk_tw/{code}/{k_type}"
        print(f"[DEBUG] Fetching K-Line (TW): {url_tw}")
        
        try:
            response = requests.get(url_tw, timeout=10)
            # Log non-200 but don't raise immediately to allow OTC fallback check
            if response.status_code != 200:
                print(f"[DEBUG] TW K-Line failed: {response.status_code}")
                data = {}
            else:
                data = response.json()
            
            # 解析數據
            # 結構: {"chart": {"data": [{"DataPrice": [...], "_ItemName": [...]}]}}
            
            chart_data = data.get("chart", {}).get("data", [])
            if not chart_data:
                print("[DEBUG] TW K-Line empty, trying OTC...")
                # 可能是上櫃，嘗試 stk_otc
                url_otc = f"https://wantrich.chinatimes.com/api/stock/stk_otc/{code}/{k_type}"
                print(f"[DEBUG] Fetching K-Line (OTC): {url_otc}")
                try:
                    response_otc = requests.get(url_otc, timeout=10)
                    if response_otc.status_code == 200:
                        data = response_otc.json()
                        chart_data = data.get("chart", {}).get("data", [])
                    else:
                         print(f"[DEBUG] OTC K-Line failed: {response_otc.status_code}")
                except Exception as ex:
                    print(f"[DEBUG] OTC fetch error: {ex}")

            if not chart_data:
                error_msg = f"未找到股票 {code} 的 K 線數據。請確認代碼是否正確（例如 2330），或嘗試改用其他工具 (如 financial.get_verified_price)。"
                print(f"[DEBUG] {error_msg}")
                return ToolResult(
                    data=[],
                    raw={"message": "No chart data found", "hint": error_msg},
                    used_cache=False,
                    cost=0.0,
                    citations=[]
                )
            
            price_data = chart_data[0].get("DataPrice", [])
            
            # 格式化輸出
            # Mapping: 0:Date, 1:Open, 2:High, 3:Low, 4:Close, 5:Vol
            formatted_data = []
            for row in price_data[-30:]: # 取最近30筆，避免 Token 爆炸
                try:
                    ts = row[0]
                    date_str = time.strftime('%Y-%m-%d', time.localtime(ts))
                    formatted_data.append({
                        "date": date_str,
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5]
                    })
                except:
                    continue
                    
            return ToolResult(
                data=formatted_data,
                raw={"total_count": len(price_data), "returned_count": len(formatted_data)},
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes K-Line",
                    "title": f"Stock {code} K-Line History",
                    "url": url_tw,
                    "snippet": f"Last close: {formatted_data[-1]['close'] if formatted_data else 'N/A'}"
                }]
            )
            
        except Exception as e:
            logger.error(f"ChinaTimes kline failed: {e}")
            return ToolResult(
                data=[],
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
        return "獲取特定個股的相關新聞報導列表。需提供股票代碼與中文名稱。"

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
        # Auto-correct aliases
        if "code" not in params:
            for alias in ["symbol", "ticker", "id", "coid", "stock_id"]:
                if alias in params:
                    params["code"] = params[alias]
                    break
                    
        if "code" not in params:
            raise ValueError("缺少必要參數: code")
        if "name" not in params:
            # Try to infer name or allow partial
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

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
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


class ChinaTimesMarketIndexAdapter(BaseToolAdapter):
    """
    中時財經 - 大盤指數工具
    """

    @property
    def name(self) -> str:
        return "chinatimes.market_index"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "獲取台灣大盤加權指數與櫃買指數 (OTC) 的即時與歷史概況。"

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
        return 300  # 5 分鐘

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }

    def validate(self, params: Dict) -> None:
        pass

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        return "chinatimes_market_index"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes MarketIndex API Error: {http_status} - {body}")

    def invoke(self, **kwargs) -> ToolResult:
        # Fallback to stock_rt for Taiex (IX0001) as tpex_otc endpoint is unstable (500)
        url = "https://wantrich.chinatimes.com/api/stock_rt/IX0001"
        try:
            response = requests.get(url, timeout=10)
            # Response 200 may still contain errorMsg in JSON
            # e.g., {"errorMsg":"IX0001 isn't exist in redis"}
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
                
            data = response.json()
            if "errorMsg" in data:
                 raise Exception(f"API Error: {data['errorMsg']}")
            
            return ToolResult(
                data=data,
                raw={"response_sample": str(data)[:200]},
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes Market Index",
                    "title": "Taiex Index (IX0001)",
                    "url": url,
                    "snippet": f"Taiex Index Price: {data.get('Price', 'N/A')}"
                }]
            )
        except Exception as e:
            logger.error(f"ChinaTimes market_index failed: {e}")
            return ToolResult(
                data={},
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )


class ChinaTimesMarketRankingsAdapter(BaseToolAdapter):
    """
    中時財經 - 市場排行工具 (Top 10)
    """

    @property
    def name(self) -> str:
        return "chinatimes.market_rankings"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "查詢台股市場排行資訊 (上市/上櫃)。包含漲跌幅排行、成交量排行等市場動態。"

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
        return 300  # 5 分鐘

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                     "mkt_type": {
                        "type": "string",
                        "description": "市場類型 (TSE=上市, OTC=上櫃)",
                        "default": "TSE",
                        "enum": ["TSE", "OTC"]
                    }
                },
                "required": []
            }
        }

    def validate(self, params: Dict) -> None:
        pass

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        mkt = params.get("mkt_type", "TSE")
        return f"chinatimes_market_rankings:{mkt}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes MarketRankings API Error: {http_status} - {body}")

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        mkt_type = params.get("mkt_type", "TSE")
        
        # Mapping to specific API endpoints or using tpex_top10
        # Collection suggests: https://wantrich.chinatimes.com/api/stock_list/TSE for Top 5
        # or https://wantrich.chinatimes.com/api/tse_top10
        
        url = f"https://wantrich.chinatimes.com/api/stock_list/{mkt_type}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return ToolResult(
                data=data,
                raw={"response_sample": str(data)[:200]},
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes Rankings",
                    "title": f"{mkt_type} Market Rankings",
                    "url": url,
                    "snippet": f"Top movers and active stocks for {mkt_type}."
                }]
            )
        except Exception as e:
            logger.error(f"ChinaTimes market_rankings failed: {e}")
            return ToolResult(
                data={},
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )


class ChinaTimesSectorAdapter(BaseToolAdapter):
    """
    中時財經 - 類股分析工具
    """

    @property
    def name(self) -> str:
        return "chinatimes.sector_info"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "查詢特定類股的績效表現或其成分股列表。需提供類股代碼 (Sector ID)。"

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
        return 600  # 10 分鐘

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                     "sector_id": {
                        "type": "string",
                        "description": "類股 ID (e.g. 15 for Electronics, etc.)"
                    },
                    "action": {
                        "type": "string",
                        "description": "操作類型 (performance=類股表現, list=成分股列表)",
                        "default": "list",
                        "enum": ["performance", "list"]
                    }
                },
                "required": ["sector_id"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "sector_id" not in params:
             raise ValueError("缺少必要參數: sector_id")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        sid = params.get("sector_id", "")
        act = params.get("action", "list")
        return f"chinatimes_sector:{sid}:{act}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes Sector API Error: {http_status} - {body}")

    def invoke(self, params: Dict) -> ToolResult:
        # params = kwargs # Removed
        self.validate(params)
        sector_id = params["sector_id"]
        action = params.get("action", "list")
        
        if action == "performance":
            url = f"https://wantrich.chinatimes.com/api/sector/{sector_id}"
        else:
            url = f"https://wantrich.chinatimes.com/api/sector_list/{sector_id}/ASC"
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://wantrich.chinatimes.com/"
        }
            
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return ToolResult(
                data=data,
                raw={"response_sample": str(data)[:200]},
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes Sector Info",
                    "title": f"Sector {sector_id} {action}",
                    "url": url,
                    "snippet": f"Data for sector {sector_id} ({action})"
                }]
            )
        except Exception as e:
            logger.error(f"ChinaTimes sector_info failed: {e}")
            return ToolResult(
                data={},
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )


class ChinaTimesStockFundamentalAdapter(BaseToolAdapter):
    """
    中時財經 - 個股健診工具 (基本面/技術面總覽)
    """

    @property
    def name(self) -> str:
        return "chinatimes.stock_fundamental"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "獲取個股的基本面與技術面綜合健診報告。包含財務體質、技術指標與診斷評分。"

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
        return 3600  # 1 小時

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
        # Auto-correct aliases
        if "code" not in params:
            for alias in ["symbol", "ticker", "id", "coid", "stock_id"]:
                if alias in params:
                    params["code"] = params[alias]
                    break
        if "code" not in params:
             raise ValueError("缺少必要參數: code")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        code = params.get("code", "")
        return f"chinatimes_stock_fundamental:{code}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"ChinaTimes Fundamental API Error: {http_status} - {body}")

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        
        url = f"https://wantrich.chinatimes.com/api/stock_check/{code}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return ToolResult(
                data=data,
                raw={"response_sample": str(data)[:200]},
                used_cache=False,
                cost=0.0,
                citations=[{
                    "source": "ChinaTimes Fundamental Check",
                    "title": f"Stock {code} Fundamental Check",
                    "url": url,
                    "snippet": "Stock fundamental/technical check data."
                }]
            )
        except Exception as e:
            logger.error(f"ChinaTimes stock_fundamental failed: {e}")
            return ToolResult(
                data={},
                raw={"error": str(e)},
                used_cache=False,
                cost=0.0,
                citations=[]
            )

class ChinaTimesBaseFinancialAdapter(BaseToolAdapter):
    """
    中時財經財務報表共用基類
    """
    @property
    def auth_config(self) -> Dict:
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        return {"limit": 60, "period": 60}

    @property
    def cache_ttl(self) -> int:
        return 3600

    def validate(self, params: Dict) -> None:
        if "code" not in params:
            raise ValueError("缺少必要參數: code")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        code = params.get("code", "")
        return f"{self.name}:{code}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"{self.name} API Error: {http_status} - {body}")

class ChinaTimesBalanceSheetAdapter(ChinaTimesBaseFinancialAdapter):
    """
    中時財經 - 資產負債表
    """
    @property
    def name(self) -> str:
        return "chinatimes.balance_sheet"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return "獲取個股的資產負債表數據。回傳資產、負債與股東權益的詳細項目。"

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代碼 (e.g. 2330)"}
                },
                "required": ["code"]
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        url = f"http://10.228.7.79/api/finweb/stk_tw/{code}/f1"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                 return ToolResult(data={"error": f"API Error {response.status_code}"}, raw={}, used_cache=False, cost=0.0, citations=[])
            return ToolResult(data=response.json(), raw={}, used_cache=False, cost=0.0, citations=[{"source": self.name, "url": url}])
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={}, used_cache=False, cost=0.0, citations=[])

class ChinaTimesIncomeStatementAdapter(ChinaTimesBaseFinancialAdapter):
    """
    中時財經 - 損益表
    """
    @property
    def name(self) -> str:
        return "chinatimes.income_statement"
    
    @property
    def version(self) -> str:
        return "v1"
        
    @property
    def description(self) -> str:
        return "獲取個股的損益表數據。回傳營收、毛利、營業利益與淨利等項目。"

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代碼 (e.g. 2330)"}
                },
                "required": ["code"]
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        url = f"http://10.228.7.79/api/finweb/stk_tw/{code}/f2"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                 return ToolResult(data={"error": f"API Error {response.status_code}"}, raw={}, used_cache=False, cost=0.0, citations=[])
            return ToolResult(data=response.json(), raw={}, used_cache=False, cost=0.0, citations=[{"source": self.name, "url": url}])
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={}, used_cache=False, cost=0.0, citations=[])

class ChinaTimesCashFlowAdapter(ChinaTimesBaseFinancialAdapter):
    """
    中時財經 - 現金流量表
    """
    @property
    def name(self) -> str:
        return "chinatimes.cash_flow"
        
    @property
    def version(self) -> str:
        return "v1"
        
    @property
    def description(self) -> str:
        return "獲取個股的現金流量表數據。回傳營業、投資與籌資活動之現金流量。"

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代碼 (e.g. 2330)"}
                },
                "required": ["code"]
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        url = f"http://10.228.7.79/api/finweb/stk_tw/{code}/f3"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                 return ToolResult(data={"error": f"API Error {response.status_code}"}, raw={}, used_cache=False, cost=0.0, citations=[])
            return ToolResult(data=response.json(), raw={}, used_cache=False, cost=0.0, citations=[{"source": self.name, "url": url}])
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={}, used_cache=False, cost=0.0, citations=[])

class ChinaTimesFinancialRatiosAdapter(ChinaTimesBaseFinancialAdapter):
    """
    中時財經 - 財務比率
    """
    @property
    def name(self) -> str:
        return "chinatimes.financial_ratios"
        
    @property
    def version(self) -> str:
        return "v1"
        
    @property
    def description(self) -> str:
        return "獲取個股的關鍵財務比率。包含獲利能力、償債能力與經營能力分析。"

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代碼 (e.g. 2330)"}
                },
                "required": ["code"]
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        code = params["code"]
        url = f"http://10.228.7.79/api/finweb/stk_tw/{code}/f4"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                 return ToolResult(data={"error": f"API Error {response.status_code}"}, raw={}, used_cache=False, cost=0.0, citations=[])
            return ToolResult(data=response.json(), raw={}, used_cache=False, cost=0.0, citations=[{"source": self.name, "url": url}])
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={}, used_cache=False, cost=0.0, citations=[])