from typing import Dict, Any

def normalize_symbol(symbol: str) -> Dict[str, Any]:
    """
    統一解析股票代碼，回傳適用於各平台的格式。
    
    支援格式：
    - 2330 -> coid: 2330, yahoo: 2330.TW (預設上市)
    - 2330.TW -> coid: 2330, yahoo: 2330.TW
    - 8069.TWO -> coid: 8069, yahoo: 8069.TWO (上櫃)
    - NVDA -> coid: NVDA, yahoo: NVDA (美股)
    
    Returns:
        {
            "original": str,       # 原始輸入
            "coid": str,           # 純代碼 (用於 TEJ/TWSE)，去除後綴
            "yahoo_ticker": str,   # Yahoo 格式 (含後綴 .TW/.TWO)
            "market": str,         # 市場 (TW/US)
            "exchange": str        # 交易所 (TWSE/TPEx/US) - inferred
        }
    """
    s = symbol.strip().upper()
    
    # 預設值 (假設為美股或未知)
    result = {
        "original": symbol,
        "coid": s,
        "yahoo_ticker": s,
        "market": "US",  
        "exchange": "Unknown"
    }

    # 1. 處理帶後綴的台股 (.TW / .TWO)
    if s.endswith('.TW'):
        base = s[:-3]
        result.update({
            "coid": base,
            "yahoo_ticker": s,
            "market": "TW",
            "exchange": "TWSE"
        })
        return result
        
    if s.endswith('.TWO'):
        base = s[:-4]
        result.update({
            "coid": base,
            "yahoo_ticker": s,
            "market": "TW",
            "exchange": "TPEx" # Taipei Exchange (OTC)
        })
        return result

    # 2. 處理帶前綴的格式 (TW:2330, TWO:8069)
    if ':' in s:
        prefix, code = s.split(':', 1)
        if prefix in ('TW', 'TSE'):
            result.update({
                "coid": code,
                "yahoo_ticker": f"{code}.TW",
                "market": "TW",
                "exchange": "TWSE"
            })
            return result
        if prefix in ('TWO', 'OTC'):
            result.update({
                "coid": code,
                "yahoo_ticker": f"{code}.TWO",
                "market": "TW",
                "exchange": "TPEx"
            })
            return result

    # 3. 純數字處理 (假設為台股)
    # 限制：若未指定後綴，預設視為 .TW (TWSE)。這是因為無法從純數字判斷是上市或上櫃。
    # 建議使用者輸入完整代碼以獲得精確結果。
    if s.isdigit() and 3 <= len(s) <= 6:
        result.update({
            "coid": s,
            "yahoo_ticker": f"{s}.TW", # Default assumption
            "market": "TW",
            "exchange": "TWSE"     # Default assumption
        })
        return result

    return result