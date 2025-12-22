import requests
import re
import json
import time
from typing import List, Dict, Any

class ChinatimesProbe:
    """中時新聞網股市 API 探測器"""
    
    BASE_URL = "https://wantrich.chinatimes.com"
    STOCK_ID = "2330"
    
    # 模擬瀏覽器行為
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://wantrich.chinatimes.com/tw-market/listed/stock/2330"
    }

    def __init__(self, stock_id="2330"):
        self.stock_id = stock_id
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def log(self, level: str, message: str, **kwargs):
        """簡單的結構化日誌輸出"""
        context = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        print(f"[{level}] {message} {context}")

    def probe_html_source(self):
        """步驟 1 & 2: 請求主頁面並尋找 JavaScript 中的 API 痕跡"""
        target_url = f"{self.BASE_URL}/tw-market/listed/stock/{self.stock_id}"
        self.log("INFO", "開始分析主頁面 HTML", url=target_url)

        try:
            response = self.session.get(target_url, timeout=10)
            self.log("INFO", "主頁面請求完成", status_code=response.status_code, size=len(response.text))

            if response.status_code != 200:
                self.log("ERROR", "主頁面請求失敗")
                return

            # Regex 模式: 尋找常見的 API 調用特徵
            # 1. 尋找 /api/ 開頭的字串
            # 2. 尋找 .json 結尾的字串
            # 3. 尋找 ajax/fetch 調用
            patterns = [
                r'["\'](/api/[^"\']+)["\']',  # '/api/...'
                r'["\']([^"\']+\.json)["\']',  # '... .json'
                r'url\s*:\s*["\']([^"\']+)["\']', # url: '...'
            ]

            found_urls = set()
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    # 過濾掉明顯不是 API 的資源 (css, png 等)
                    if not any(ext in match.lower() for ext in ['.css', '.png', '.jpg', '.js', '.gif']):
                        found_urls.add(match)

            if found_urls:
                print("\n🔍 [Regex] 在 HTML 原始碼中發現的潛在 URL:")
                for url in sorted(found_urls):
                    print(f"   - {url}")
            else:
                self.log("WARN", "Regex 未發現明顯的 API 路徑")

        except Exception as e:
            self.log("ERROR", "主頁面分析發生錯誤", error=str(e))

    def probe_subpages(self):
        """步驟 3: 尋找子頁面連結"""
        target_url = f"{self.BASE_URL}/tw-market/listed/stock/{self.stock_id}"
        print(f"\n🔗 [Links] 分析主頁面導航連結: {target_url}")
        
        try:
            response = self.session.get(target_url, timeout=10)
            if response.status_code != 200:
                return

            # 尋找所有包含 stock_id 的連結
            # 例如: href="/tw-market/listed/stock/2330/financial"
            pattern = fr'href=["\'](/tw-market/listed/stock/{self.stock_id}/[^"\']+)["\']'
            links = set(re.findall(pattern, response.text))
            
            if links:
                for link in sorted(links):
                    print(f"   - 子頁面: {link}")
                    # 順便猜測這些子頁面是否對應 API
                    # 例如 /tw-market/.../financial -> /api/stock/stk_tw/.../financial
                    suffix = link.split('/')[-1]
                    self.fuzz_targets.append(suffix)
            else:
                self.log("WARN", "未發現明顯的子頁面連結")
                
        except Exception as e:
            self.log("ERROR", "子頁面分析失敗", error=str(e))

    def probe_api_endpoints(self):
        """步驟 4: 主動探測 API (包含 Fuzzing)"""
        print("\n🚀 [Probe] 開始主動探測 API 路徑...")
        
        # 基礎已知模式
        base_api = f"/api/stock/stk_tw/{self.stock_id}"
        
        # Fuzzing 列表
        candidates = [
            "k1", "k", "quote", "realtime", "info", "detail", # 基本
            "financial", "finance", "revenue", "eps", # 財報
            "dividend", "yield", # 股利
            "institutional", "3insti", "trust", "foreign", # 籌碼
            "margin", "short", # 信用
            "news", "announcement" # 新聞
        ]
        
        # 加入從子頁面發現的後綴
        if hasattr(self, 'fuzz_targets'):
            candidates.extend(self.fuzz_targets)
            
        # 去重
        candidates = sorted(list(set(candidates)))

        for suffix in candidates:
            # 構造類似已知成功的路徑結構
            endpoint = f"{base_api}/{suffix}"
            full_url = f"{self.BASE_URL}{endpoint}"
            
            try:
                time.sleep(0.5) # 增加延遲
                
                # 某些 API 嚴格檢查 Referer
                headers = self.HEADERS.copy()
                headers['Referer'] = f"https://wantrich.chinatimes.com/tw-market/listed/stock/{self.stock_id}"
                
                response = self.session.get(full_url, headers=headers, timeout=5)
                status = response.status_code
                
                if status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    is_json = 'application/json' in content_type
                    
                    if is_json:
                        try:
                            data = response.json()
                            if not data:
                                print(f"⚠️ [200] {endpoint:<40} | Empty JSON")
                            else:
                                preview = json.dumps(data, ensure_ascii=False)[:100] + "..."
                                print(f"✅ [200] {endpoint:<40} | JSON: Yes | {preview}")
                        except:
                            print(f"⚠️ [200] {endpoint:<40} | Invalid JSON Body")
                    else:
                        # 解析 HTML Title 以識別 Soft 404
                        title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                        title = title_match.group(1).strip() if title_match else "No Title"
                        # 只顯示非預設標題的結果，過濾雜訊
                        if "旺得富" not in title and "中時" not in title:
                            print(f"⚠️ [200] {endpoint:<40} | HTML: {title[:20]}")
                        elif suffix == "k1": # k1 是我們已知的，特別關注它為什麼失敗
                             print(f"❌ [200] {endpoint:<40} | Failed (Got HTML Page: {title[:20]})")
                        
                elif status == 404:
                    pass
                elif status == 403:
                    print(f"🚫 [403] {endpoint:<40} | Forbidden")
                else:
                    print(f"❓ [{status}] {endpoint:<40}")

            except Exception as e:
                print(f"💥 [ERR] {endpoint:<40} | {str(e)}")

    def run(self):
        self.fuzz_targets = []
        print(f"=== 開始探測 Chinatimes 股票 API (Target: {self.stock_id}) ===")
        self.probe_html_source()
        self.probe_subpages() # 新增: 分析子頁面
        self.probe_api_endpoints()
        print("\n=== 探測結束 ===")

if __name__ == "__main__":
    probe = ChinatimesProbe(stock_id="2330")
    probe.run()