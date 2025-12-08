from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
from .tool_adapter import ToolAdapter

class WebFetchAdapter(ToolAdapter):
    """
    Adapter for fetching and parsing web page content.
    """
    
    @property
    def name(self) -> str:
        return "common.web_fetch"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return "抓取指定 URL 的網頁內容並提取純文字。當你需要閱讀具體網頁、新聞報導或報告全文時使用。"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的網頁 URL (必須以 http:// 或 https:// 開頭)"
                }
            },
            "required": ["url"]
        }
    
    def describe(self) -> Dict[str, Any]:
        """回傳工具的詳細描述"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        url = kwargs.get("url")
        if not url:
            return {"error": "Missing 'url' parameter"}
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Simple text extraction
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text(separator='\n', strip=True)
            
            # Truncate if too long (to prevent context overflow)
            MAX_LEN = 5000
            if len(text) > MAX_LEN:
                text = text[:MAX_LEN] + f"\n...(Truncated, total length: {len(text)})"
                
            return {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "content": text
            }
            
        except Exception as e:
            return {"error": f"Failed to fetch content: {str(e)}"}
