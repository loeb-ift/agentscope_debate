
import asyncio
from typing import Dict, Any, List
import pandas as pd
from bs4 import BeautifulSoup
from api.redis_client import get_redis_client
import json
import os

class StockQAdapter:
    """
    Adapter for StockQ.org using Playwright for web scraping.
    Provides real-time global market indices and commodities.
    """
    def __init__(self):
        self.base_url = "https://www.stockq.org"
        self.name = "stockq"
        self._redis_client = get_redis_client()
        self.cache_ttl = 300 # 5 minutes

    async def _fetch_page(self, path: str = "") -> str:
        """Fetch page content using browser MCP tool if possible, or fallback to direct playwright if env allows."""
        # For this implementation, we will use the internal browser tool if available via tool_invoker
        # OR use a direct requests approach if StockQ doesn't block it (easier for structured data).
        # StockQ is relatively simple HTML, so requests + custom headers often works.
        import requests
        url = f"{self.base_url}/{path}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"

    def _parse_table(self, html: str, table_index: int = 0) -> List[Dict[str, Any]]:
        """Parse HTML tables into structured JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('table', class_='market')
        if not tables:
            # Try alternate selector if 'market' class isn't found
            tables = soup.find_all('table')
            
        if not tables or table_index >= len(tables):
            return []
            
        target_table = tables[table_index]
        rows = target_table.find_all('tr')
        
        data = []
        headers = []
        
        for i, row in enumerate(rows):
            cols = row.find_all(['th', 'td'])
            cols = [ele.text.strip() for ele in cols]
            
            if i == 0:
                headers = cols
                continue
                
            if len(cols) == len(headers):
                entry = dict(zip(headers, cols))
                data.append(entry)
                
        return data

class StockQMarketSummary(StockQAdapter):
    def __init__(self):
        super().__init__()
        self.name = "stockq.market_summary"
        self.description = "Get a real-time summary of global market indices (US, Europe, Asia), Commodities, and Currencies from StockQ. Contains links to deep index details."
        self.schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category to focus on: 'index', 'commodity', 'currency'.",
                    "enum": ["index", "commodity", "currency"]
                }
            }
        }

    def _parse_summary_with_links(self, html: str) -> List[Dict[str, Any]]:
        """Special parser for summary table that extracts link IDs for Level 2 access."""
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('table', class_='market')
        if not tables: tables = soup.find_all('table')
        if len(tables) < 2: return []
        
        target_table = tables[1]
        rows = target_table.find_all('tr')
        
        data = []
        headers = ["指數", "點數", "漲跌", "百分比", "時間", "Level2_ID"]
        
        for i, row in enumerate(rows):
            if i == 0: continue
            cols = row.find_all(['td'])
            if len(cols) < 5: continue
            
            row_data = [c.text.strip() for c in cols]
            
            # Extract Link if exists (e.g. index/MS115.php)
            link = row.find('a', href=True)
            l2_id = ""
            if link:
                href = link['href']
                if "index/" in href:
                    l2_id = href.split('/')[-1].replace('.php', '')
            
            row_data.append(l2_id)
            if len(row_data) == len(headers):
                data.append(dict(zip(headers, row_data)))
        return data

    def describe(self) -> str:
        return self.description

    def invoke(self, category: str = None) -> Dict[str, Any]:
        # Implementation uses sync wrapper for async fetch
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        html = loop.run_until_complete(self._fetch_page())
        
        if html.startswith("Error"):
            return {"error": html}
            
        # Parse multiple tables on home page
        indices = self._parse_summary_with_links(html)
        
        return {
            "source": "StockQ.org",
            "timestamp_retrieved": pd.Timestamp.now().isoformat(),
            "indices": indices[:20],
            "instruction": "Use 'stockq.index_details' with Level2_ID for historical data or deeper analysis."
        }

class StockQIndexDetails(StockQAdapter):
    def __init__(self):
        super().__init__()
        self.name = "stockq.index_details"
        self.description = "Get detailed real-time quotes for a specific market region (e.g., 'asia', 'us', 'europe')."
        self.schema = {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Region name ('us', 'asia', 'europe', 'commodity', 'currency') OR a specific Level2_ID (e.g. 'MS115' for deeper index info).",
                    "default": "asia"
                }
            },
            "required": ["region"]
        }

    def describe(self) -> str:
        return self.description

    def invoke(self, region: str = "asia") -> Dict[str, Any]:
        path_map = {
            "us": "market/usa.php",
            "asia": "market/asia.php",
            "europe": "market/europe.php",
            "commodity": "commodity/",
            "currency": "currency/"
        }
        
        # Check if region is actually a Level 2 ID (e.g. MS115)
        if region.isalnum() and len(region) < 10 and region.lower() not in path_map:
            path = f"index/{region}.php"
        else:
            path = path_map.get(region.lower(), "market/asia.php")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        html = loop.run_until_complete(self._fetch_page(path))
        
        if html.startswith("Error"):
            return {"error": html}
            
        data = self._parse_table(html, 1)
        
        # If Level 2, try to extract more info like "Historical Table" or "Components"
        # StockQ index pages often have historical data in later tables
        historical_data = []
        if "index/" in path:
            historical_data = self._parse_table(html, 2) # Usually 2nd or 3rd table
            
        return {
            "target": region,
            "url": f"https://www.stockq.org/{path}",
            "current_quotes": data[:10],
            "historical_preview": historical_data[:10] if historical_data else []
        }
