"""TEJ REST API adapter implementation (Datatables endpoint).

Docs: https://api.tej.com.tw/datatables.html
Example: GET https://api.tej.com.tw/api/datatables/TRAIL/TAIACC.json?api_key=<YOURAPIKEY>
"""
from __future__ import annotations
import os
from typing import Any, Dict, Optional

import re
import requests

from .tool_adapter import ToolAdapter
from .base import ToolResult, UpstreamError
from mars.types.errors import ToolRecoverableError, ToolTerminalError, ToolFatalError
from worker.utils.symbol_utils import normalize_symbol

class TEJBaseAdapter(ToolAdapter):
    """Base adapter for TEJ API interactions."""
    
    def __init__(self, base_url: str = "https://api.tej.com.tw/api/datatables", api_key: Optional[str] = None, timeout_sec: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("TEJ_API_KEY")
        self.timeout_sec = timeout_sec
        self.auth_config = {"type": "api_key", "in": "query", "param": "api_key"}
        self.rate_limit_config = {"tps": 5, "burst": 10}
        self.cache_ttl = 6 * 60 * 60  # 6 hours
    def _flatten_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to flatten nested tool parameters from Agent hallucinations."""
        if "params" in params and isinstance(params["params"], dict) and "tool" in params:
             print(f"DEBUG: Auto-correcting nested params: {params['params']}")
             params.update(params["params"])
        return params


    def auth(self, req: Dict[str, Any]) -> Dict[str, Any]:
        token = self.api_key
        print(f"DEBUG: Using TEJ API Key: {token}")
        if not token:
            raise UpstreamError(code="ERR-AUTH", http_status=401, message="TEJ_API_KEY missing")
        q = req.get("params", {})
        q["api_key"] = token
        req["params"] = q
        return req

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def _build_url(self, db: str, table: str) -> str:
        return f"{self.base_url}/{db}/{table}.json"

    def _execute_query(self, db: str, table: str, params: Dict[str, Any], filters: Optional[Dict[str, Any]] = None) -> ToolResult:
        # Hotfix for nested parameters from potential Agent hallucination
        if "params" in params and isinstance(params["params"], dict) and "tool" in params:
             print(f"DEBUG: Auto-correcting nested params for {table}: {params['params']}")
             params.update(params["params"])

        # Auto-correct aliases for 'coid'
        if "coid" not in params:
            for alias in ["company_id", "id", "symbol", "ticker"]:
                if alias in params:
                    params["coid"] = params[alias]
                    if filters and "coid" in filters and filters["coid"] is None:
                        filters["coid"] = params[alias] # Update filter if it was passed as None key
                    break
        
        # [Fix Phase 20] Use robust normalization
        if "coid" in params and isinstance(params["coid"], str):
            try:
                norm = normalize_symbol(params["coid"])
                params["coid"] = norm["coid"]
            except Exception as e:
                print(f"Symbol normalization warning: {e}")
                # Fallback to simple strip (Handle both TWSE and OTC suffixes)
                if params["coid"].endswith(".TW"):
                    params["coid"] = params["coid"].replace(".TW", "")
                elif params["coid"].endswith(".TWO"):
                    params["coid"] = params["coid"].replace(".TWO", "")

            # Also update filters if they use coid
            if filters and "coid" in filters and isinstance(filters["coid"], str):
                 filters["coid"] = params["coid"]

        url = self._build_url(db, table)
        query: Dict[str, Any] = {}
        
        # TEJ API uses opts.limit and opts.offset for pagination to avoid conflict with column names
        if "limit" in params:
            query["opts.limit"] = params["limit"]
        # else:
        #     query["opts.limit"] = 50 # Default limit (Disabled to avoid 400 errors on some tables)
            
        if "offset" in params:
            query["opts.offset"] = params["offset"]
        
        # Handle filters
        if filters:
            for k, v in filters.items():
                if v is not None:
                    query[k] = v
                elif k in params:
                    query[k] = params[k]
                
        # Handle date range if provided in params but not in filters
        if "start_date" in params and "mdate.gte" not in query:
             query["mdate.gte"] = params["start_date"]
        if "end_date" in params and "mdate.lte" not in query:
             query["mdate.lte"] = params["end_date"]

        req = self.auth({"headers": {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}, "params": query})
        
        try:
            print(f"DEBUG: Requesting {url}")
            print(f"DEBUG: Params: {req['params']}")
            resp = requests.get(url, headers=req["headers"], params=req["params"], timeout=self.timeout_sec)
        except requests.RequestException as e:
             raise UpstreamError(code="ERR-NET", http_status=500, message=str(e))

        if resp.status_code != 200:
            body = None
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text[:200]}
            print(f"DEBUG: Response body: {body}")
            raise self.map_error(resp.status_code, body)

        raw = resp.json()
        # print(f"DEBUG: Raw response from TEJ: {raw}") # Reduce noise if large
        
        rows = raw.get("data")
        if rows is None:
            # Check for datatable wrapper (common in some TEJ endpoints)
            datatable = raw.get("datatable")
            if isinstance(datatable, dict):
                rows = datatable.get("data")
        
        if rows is None:
            rows = []
            
        print(f"DEBUG: TEJ API returned {len(rows)} rows.")
        if len(rows) == 0:
             print(f"WARNING: TEJ API returned 0 rows for {url}. Check date range and filters.")
             # [Fix] Raise error if empty to trigger Agent retry/fallback
             # Only if not a search query (company_info might return empty if not found)
             if "TAPRCD" in table or "TASALE" in table or "TAIM1A" in table:
                 # [Phase 2 Update] Stronger Fallback Guidance
                 fallback_msg = ""
                 if "TAPRCD" in table: # Stock Price
                     fallback_msg = "\n⚠️ **嚴重警告**：TEJ 股價數據為空。請立即改用 `financial.get_verified_price` (推薦) 或 `yahoo.stock_price` 獲取數據。"
                 
                 raise ToolRecoverableError(
                     message=f"❌ TEJ 查詢成功但無資料 ({db}/{table})。可能是日期範圍內無交易，或資料庫未更新。{fallback_msg}\n建議行動：\n1. 改用備用工具 (如 financial.get_verified_price)\n2. 檢查日期範圍 (不要查詢未來日期)",
                     metadata={"hint": "use_fallback_tools", "tool": "tej", "table": table}
                 )

        data = {
            "db": db,
            "table": table,
            "limit": query.get("opts.limit", 50),
            "offset": query.get("opts.offset", 0),
            "rows": rows,
        }

        # [Fix Phase 2] Normalize result and check warnings (e.g. date_span_too_large)
        warnings = []
        # Extract warnings from meta or response if TEJ provides them there
        if raw.get("meta") and "warnings" in raw["meta"]:
             warnings.extend(raw["meta"]["warnings"])
        
        # Check specific error patterns in the 'rows' themselves or raw response
        if "warnings" in raw:
             if isinstance(raw["warnings"], list):
                 warnings.extend(raw["warnings"])
             else:
                 warnings.append(str(raw["warnings"]))
        
        # Construct tool_data dummy for _normalize_tej_result
        tool_data_dummy = {"group": "tej"}
        
        # This call will raise ToolRecoverableError if critical warnings found
        normalized_data = self._normalize_tej_result(tool_data_dummy, {"data": rows, "meta": raw.get("meta")}, warnings)
        
        # Re-package normalized data back into our 'data' structure
        # _normalize_tej_result returns { "data": [...], "meta": ..., "warnings": ... }
        if "data" in normalized_data:
            data["rows"] = normalized_data["data"]

        citations = [{
            "title": f"TEJ {db}/{table}",
            "url": url,
            "snippet": f"limit={data['limit']}, rows={len(data['rows'])}",
            "source": "TEJ"
        }]
        return ToolResult(data=data, raw=raw, used_cache=False, cost=None, citations=citations)

    def map_error(self, http_status: int, body: Any) -> Exception:
        message = str(body)
        if isinstance(body, dict) and "error" in body:
             message = body["error"]

        if http_status == 401:
            return ToolFatalError(f"TEJ Auth Error (401): {message}", metadata={"http_status": 401})
        elif http_status == 403:
            return ToolFatalError(f"TEJ Access Denied (403): {message}", metadata={"http_status": 403})
        elif http_status == 404:
            # 404 might be wrong endpoint or truly not found. For TEJ datatables, it usually means table not found?
            # Or resource not found. Let's treat as Terminal for this path.
            return ToolTerminalError(f"Resource Not Found (404): {message}", metadata={"http_status": 404})
        elif http_status == 429:
            return ToolRecoverableError(f"Rate Limit Exceeded (429): {message}. Please retry later.", metadata={"retry_after": 5})
        
        # Default fallback
        return UpstreamError(code="ERR-UNKNOWN", http_status=http_status, message=message)

    def _normalize_tej_result(self, tool_data: Dict[str, Any], result: Dict[str, Any], warnings: list) -> Dict[str, Any]:
        """將 TEJ 結果標準化為 { data: [...] }，並附加 warnings。"""
        group = tool_data.get("group") or ""
        provider = getattr(tool_data.get("instance"), "provider", "")
        is_tej = (group == "tej") or (str(provider).lower() == "tej")
        if not is_tej or not isinstance(result, dict):
            # 非 TEJ 或非 dict，直接返回
            if warnings:
                if isinstance(result, dict):
                    result["warnings"] = warnings
            return result
        # 嘗試抽取資料陣列
        data = None
        if isinstance(result.get("data"), list):
            data = result.get("data")
            meta = result.get("meta")
        else:
            dt = result.get("datatable") if isinstance(result.get("datatable"), dict) else None
            data = dt.get("data") if isinstance(dt and dt.get("data"), list) else None
            meta = (dt.get("meta") if isinstance(dt, dict) else None)
        
        # [CRITICAL FIX] TEJ Error Guard
        # Check warnings FIRST before returning any data (even empty list)
        if warnings:
            for w in warnings:
                if "date_span_too_large" in str(w):
                    raise ToolRecoverableError(
                        message="查詢失敗：TEJ 拒絕處理此請求，原因為「日期範圍過大 (date_span_too_large)」。請務必將日期範圍縮小至 90 天以內（例如：2024-01-01 到 2024-03-31），並使用多次查詢來獲取長週期數據。",
                        metadata={"hint": "shrink_date_range", "max_days": 90}
                    )

        if isinstance(data, list):
            # [Smart Truncation]
            MAX_ROWS_TO_RETURN = 10
            if len(data) > MAX_ROWS_TO_RETURN:
                original_count = len(data)
                # Take last 10 (assuming ascending order which is typical for time series)
                data = data[-MAX_ROWS_TO_RETURN:]
                warnings.append(f"truncated: showing last {MAX_ROWS_TO_RETURN} of {original_count} rows. Use date filter to narrow down.")
            
            out = {"data": data}
            if meta is not None:
                out["meta"] = meta
            if warnings:
                out["warnings"] = warnings
            return out
            
        # 無法標準化，回傳原始並帶警示
        if warnings:
            result["warnings"] = warnings
        return result

class TEJCompanyInfo(TEJBaseAdapter):
    name = "tej.company_info"
    version = "v1"
    description = """查詢上市櫃公司基本資料 (TRAIL/AIND)
    主要欄位: 公司代碼(coid)、公司簡稱(cname)、產業別(ind_code)、成立日期(found_date)、
    上市日期(list_date)、董事長(chairman)、總經理(general_manager)、實收資本額(capital)、
    員工人數(emp_num)、營業項目(business_scope)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)

        coid = kwargs.get("coid")
        # [Config] Use TRAIL (Trial) by default, allow override to TWN via env var
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "AIND", params=kwargs, filters={"coid": coid})

class TEJStockPrice(TEJBaseAdapter):
    name = "tej.stock_price"
    version = "v1"
    description = """查詢上市櫃未調整股價日資料 (TRAIL/TAPRCD)
    主要欄位: 年月日(mdate)、開盤價(open_d)、最高價(high_d)、最低價(low_d)、收盤價(close_d)、
    成交量(volume)、成交值(amount)、報酬率(roi)、週轉率(turnover)、本益比(per_tse/per_tej)、
    股價淨值比(pbr_tse/pbr_tej)、市值(mv)、漲跌停標記(limit)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAPRCD", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJMonthlyRevenue(TEJBaseAdapter):
    name = "tej.monthly_revenue"
    version = "v1"
    description = """查詢上市櫃月營收盈餘資料 (TRAIL/TASALE)
    主要欄位: 年月(mdate)、單月營收(sales)、累計營收(sales_acc)、月增率(mom)、年增率(yoy)、
    累計年增率(yoy_acc)、單季營收(sales_q)、季增率(qoq)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TASALE", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJInstitutionalHoldings(TEJBaseAdapter):
    name = "tej.institutional_holdings"
    version = "v1"
    description = """查詢三大法人買賣超資料 (TRAIL/TATINST1)
    主要欄位: 年月日(mdate)、外資買進(fini_buy)、外資賣出(fini_sell)、外資買賣超(fini_net)、
    投信買進(trust_buy)、投信賣出(trust_sell)、投信買賣超(trust_net)、
    自營商買進(dealer_buy)、自營商賣出(dealer_sell)、自營商買賣超(dealer_net)、
    三大法人合計買賣超(inst_net)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TATINST1", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJMarginTrading(TEJBaseAdapter):
    name = "tej.margin_trading"
    version = "v1"
    description = """查詢融資融券資料 (TRAIL/TAGIN)
    主要欄位: 年月日(mdate)、融資買進(margin_buy)、融資賣出(margin_sell)、融資餘額(margin_balance)、
    融資使用率(margin_ratio)、融券買進(short_buy)、融券賣出(short_sell)、融券餘額(short_balance)、
    融券使用率(short_ratio)、資券相抵(offset)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAGIN", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJForeignHoldings(TEJBaseAdapter):
    name = "tej.foreign_holdings"
    version = "v1"
    description = """查詢外資法人持股資料 (TRAIL/TAQFII)
    主要欄位: 年月日(mdate)、外資持股數(fini_hold)、外資持股率(fini_hold_ratio)、
    外資可投資上限(fini_limit)、外資可投資餘額(fini_remain)、外資持股市值(fini_mv)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAQFII", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFinancialSummary(TEJBaseAdapter):
    name = "tej.financial_summary"
    version = "v1"
    description = """查詢 IFRS 以合併為主簡表累計資料 (TRAIL/TAIM1A)
    主要欄位: 年季(mdate)、營業收入(revenue)、營業成本(cogs)、營業毛利(gross_profit)、
    營業費用(operating_expense)、營業利益(operating_income)、稅前淨利(ebt)、
    稅後淨利(net_income)、每股盈餘(eps)、總資產(assets)、總負債(liabilities)、
    股東權益(equity)、每股淨值(bps)、ROE、ROA 等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330'). Aliases: company_id, id, ticker"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": [] # Handled dynamically
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        # [Optimization] Default to include self-assessed data for latest info
        if "include_self_acc" not in kwargs:
            kwargs["include_self_acc"] = "Y"
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAIM1A", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFundNAV(TEJBaseAdapter):
    name = "tej.fund_nav"
    version = "v1"
    description = """查詢基金淨值日資料 (TRAIL/TANAV)
    主要欄位: 年月日(mdate)、基金代碼(fund_id)、淨值(nav)、累計報酬率(return_acc)、
    規模(fund_size)、受益權單位數(units)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金統編/代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TANAV", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJShareholderMeeting(TEJBaseAdapter):
    name = "tej.shareholder_meeting"
    version = "v1"
    description = """查詢股東會事項資料 (TRAIL/TAMT)
    主要欄位: 年度(year)、股東會日期(meeting_date)、現金股利(cash_div)、股票股利(stock_div)、
    盈餘轉增資(cap_increase)、公積金轉增資(reserve_increase)、除息交易日(ex_date)、
    除權交易日(ex_right_date)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAMT", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFundBasicInfo(TEJBaseAdapter):
    name = "tej.fund_basic_info"
    version = "v1"
    description = """查詢基金基本資料 (TRAIL/TAATT)
    主要欄位: 基金代碼(fund_id)、基金名稱(fund_name)、基金類型(fund_type)、
    成立日(found_date)、計價幣別(currency)、基金規模(fund_size)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金統編/代碼. Aliases: company_id, id"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAATT", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundInfo(TEJBaseAdapter):
    name = "tej.offshore_fund_info"
    version = "v1"
    description = """查詢境外基金基本資料 (TRAIL/TAOFATT)
    主要欄位: 基金代碼(coid)、基金名稱(fund_name)、發行公司(master_company)、
    註冊地(registered_location)、計價幣別(currency)、成立日期(found_date)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFATT", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundDividend(TEJBaseAdapter):
    name = "tej.offshore_fund_dividend"
    version = "v1"
    description = """查詢境外基金配息/股息資料 (TRAIL/TAOFCAN)
    主要欄位: 除息日(ex_date)、發放日(pay_date)、配息金額(dividend)、
    幣別(currency)、配息頻率(frequency)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFCAN", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundHoldingsRegion(TEJBaseAdapter):
    name = "tej.offshore_fund_holdings_region"
    version = "v1"
    description = """查詢境外基金區域持股配置 (TRAIL/TAOFIVA)
    主要欄位: 持股區域(region)、投資比重(percentage)、資料日期(mdate)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFIVA", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundHoldingsIndustry(TEJBaseAdapter):
    name = "tej.offshore_fund_holdings_industry"
    version = "v1"
    description = """查詢境外基金產業持股配置 (TRAIL/TAOFIVP)
    主要欄位: 產業類別(industry)、投資比重(percentage)、資料日期(mdate)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFIVP", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundNAVRank(TEJBaseAdapter):
    name = "tej.offshore_fund_nav_rank"
    version = "v1"
    description = """查詢境外基金淨值與排名統計 (TRAIL/TAOFMNV)
    主要欄位: 年月(mdate)、淨值(nav)、同類型排名(rank)、總排名(total_rank)、
    月報酬率(roi_1m)、年報酬率(roi_1y)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFMNV", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundNAVDaily(TEJBaseAdapter):
    name = "tej.offshore_fund_nav_daily"
    version = "v1"
    description = """查詢境外基金每日淨值 (TRAIL/TAOFNAV)
    主要欄位: 年月日(mdate)、基金代碼(coid)、淨值(nav)、幣別(currency)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFNAV", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundSuspension(TEJBaseAdapter):
    name = "tej.offshore_fund_suspension"
    version = "v1"
    description = """查詢境外基金暫停交易/計價紀錄 (TRAIL/TAOFSUSP)
    主要欄位: 暫停日期(suspend_date)、恢復日期(resume_date)、暫停原因(reason)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFSUSP", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundPerformance(TEJBaseAdapter):
    name = "tej.offshore_fund_performance"
    version = "v1"
    description = """查詢境外基金績效表現 (TRAIL/TAOFUNDS)
    主要欄位: 期間報酬率(日/週/月/季/年)、年化標準差(std_dev)、夏普值(sharpe_ratio)、
    Beta值(beta)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOFUNDS", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJIFRSAccountDescriptions(TEJBaseAdapter):
    name = "tej.ifrs_account_descriptions"
    version = "v1"
    description = """查詢 IFRS 會計科目對照表 (TRAIL/TAIACC)
    主要欄位: 科目代碼(code)、科目名稱(name_c/name_e)、會計準則版本(version)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "科目代碼 (Optional)"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        filters = {}
        if kwargs.get("code"):
            filters["code"] = kwargs.get("code")
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAIACC", params=kwargs, filters=filters)

class TEJFinancialCoverCumulative(TEJBaseAdapter):
    name = "tej.financial_cover_cumulative"
    version = "v1"
    description = """查詢 IFRS 合併累計財報封面資訊 (TRAIL/TAIM1AA)
    主要欄位: 公司代碼(coid)、財報年月(mdate)、簽證會計師(auditor)、
    核閱/查核報告類型(report_type)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAIM1AA", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFinancialSummaryQuarterly(TEJBaseAdapter):
    name = "tej.financial_summary_quarterly"
    version = "v1"
    description = """查詢 IFRS 合併單季簡表資料 (TRAIL/TAIM1AQ)
    主要欄位: 年季(mdate)、單季營業收入(revenue_q)、單季營業成本(cogs_q)、
    單季營業毛利(gross_profit_q)、單季營業利益(operating_income_q)、
    單季稅後淨利(net_income_q)、單季 EPS(eps_q)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        # [Optimization] Default to include self-assessed data for latest info
        if "include_self_acc" not in kwargs:
            kwargs["include_self_acc"] = "Y"
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAIM1AQ", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFinancialCoverQuarterly(TEJBaseAdapter):
    name = "tej.financial_cover_quarterly"
    version = "v1"
    description = """查詢 IFRS 合併單季財報封面資訊 (TRAIL/TAIM1AQA)
    主要欄位: 公司代碼(coid)、財報年月(mdate)、簽證會計師(auditor)、
    核閱/查核報告類型(report_type)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAIM1AQA", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFuturesData(TEJBaseAdapter):
    name = "tej.futures_data"
    version = "v1"
    description = """查詢期貨資料庫 (TRAIL/TAFUTR)
    主要欄位: 年月日(mdate)、商品代碼(commodity_id)、開盤價(open)、最高價(high)、
    最低價(low)、收盤價(close)、成交量(volume)、未平倉量(open_interest)、
    結算價(settlement_price)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "期貨代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAFUTR", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOptionsBasicInfo(TEJBaseAdapter):
    name = "tej.options_basic_info"
    version = "v1"
    description = """查詢選擇權契約基本資料 (TRAIL/TAOPBAS)
    主要欄位: 契約代碼(coid)、標的物(underlying)、履約價(strike_price)、
    到期日(delivery_date)、買賣權別(call_put_type)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "選擇權代碼. Aliases: company_id, id"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOPBAS", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOptionsDailyTrading(TEJBaseAdapter):
    name = "tej.options_daily_trading"
    version = "v1"
    description = """查詢選擇權每日交易行情 (TRAIL/TAOPTION)
    主要欄位: 年月日(mdate)、契約代碼(coid)、開盤(open)、最高(high)、
    最低(low)、收盤(close)、成交量(volume)、未平倉量(oi)、結算價(settlement_price)等"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "選擇權代碼. Aliases: company_id, id"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": []
        }

    def invoke(self, **kwargs) -> ToolResult:
        kwargs = self._flatten_params(kwargs)
        db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
        return self._execute_query(db, "TAOPTION", params=kwargs, filters={"coid": kwargs.get("coid")})
