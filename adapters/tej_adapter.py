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


class TEJBaseAdapter(ToolAdapter):
    """Base adapter for TEJ API interactions."""
    
    def __init__(self, base_url: str = "https://api.tej.com.tw/api/datatables", api_key: Optional[str] = None, timeout_sec: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("TEJ_API_KEY")
        self.timeout_sec = timeout_sec
        self.auth_config = {"type": "api_key", "in": "query", "param": "api_key"}
        self.rate_limit_config = {"tps": 5, "burst": 10}
        self.cache_ttl = 6 * 60 * 60  # 6 hours

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
        url = self._build_url(db, table)
        query: Dict[str, Any] = {}
        
        # TEJ API uses opts.limit and opts.offset for pagination to avoid conflict with column names
        if "limit" in params:
            query["opts.limit"] = params["limit"]
        else:
            query["opts.limit"] = 50 # Default limit
            
        if "offset" in params:
            query["opts.offset"] = params["offset"]
        
        # Handle filters
        if filters:
            for k, v in filters.items():
                if v is not None:
                    query[k] = v
                
        # Handle date range if provided in params but not in filters
        if "start_date" in params and "mdate.gte" not in query:
             query["mdate.gte"] = params["start_date"]
        if "end_date" in params and "mdate.lte" not in query:
             query["mdate.lte"] = params["end_date"]

        req = self.auth({"headers": {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}, "params": query})
        
        try:
            print(f"DEBUG: Requesting {url} with params {req['params']}")
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
        print(f"DEBUG: Raw response from TEJ: {raw}")
        
        rows = raw.get("data")
        if rows is None:
            rows = []

        data = {
            "db": db,
            "table": table,
            "limit": query.get("opts.limit", 50),
            "offset": query.get("opts.offset", 0),
            "rows": rows,
        }
        citations = [{
            "title": f"TEJ {db}/{table}",
            "url": url,
            "snippet": f"limit={data['limit']}, rows={len(data['rows'])}",
            "source": "TEJ"
        }]
        return ToolResult(data=data, raw=raw, used_cache=False, cost=None, citations=citations)

    def map_error(self, http_status: int, body: Any) -> Exception:
        code = "ERR-UNKNOWN"
        message = str(body)
        
        if http_status == 401:
            code = "ERR-AUTH"
            message = "Invalid API Key"
        elif http_status == 403:
            code = "ERR-FORBIDDEN"
            message = "Access Denied"
        elif http_status == 404:
            code = "ERR-NOT-FOUND"
            message = "Resource Not Found"
        elif http_status == 429:
            code = "ERR-RATE-LIMIT"
            message = "Rate Limit Exceeded"
        
        if isinstance(body, dict) and "error" in body:
             message = body["error"]
             
        return UpstreamError(code=code, http_status=http_status, message=message)

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        coid = kwargs.get("coid")
        if not coid:
            raise ValueError("coid is required")
        return self._execute_query("TRAIL", "AIND", filters={"coid": coid})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAPRCD", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TASALE", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TATINST1", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAGIN", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAQFII", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼 (e.g., '2330')"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAIM1A", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "基金統編/代碼"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TANAV", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼"},
                "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "結束日期 (YYYY-MM-DD)"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAMT", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "基金統編/代碼"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAATT", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundInfo(TEJBaseAdapter):
    name = "tej.offshore_fund_info"
    version = "v1"
    description = "查詢境外基金基本資料"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFATT", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundDividend(TEJBaseAdapter):
    name = "tej.offshore_fund_dividend"
    version = "v1"
    description = "查詢境外基金股息"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFCAN", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundHoldingsRegion(TEJBaseAdapter):
    name = "tej.offshore_fund_holdings_region"
    version = "v1"
    description = "查詢境外基金持股狀況-區域"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFIVA", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundHoldingsIndustry(TEJBaseAdapter):
    name = "tej.offshore_fund_holdings_industry"
    version = "v1"
    description = "查詢境外基金持股狀況-產業"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFIVP", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundNAVRank(TEJBaseAdapter):
    name = "tej.offshore_fund_nav_rank"
    version = "v1"
    description = "查詢境外基金淨值(月排名)"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFMNV", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundNAVDaily(TEJBaseAdapter):
    name = "tej.offshore_fund_nav_daily"
    version = "v1"
    description = "查詢境外基金淨值(日)"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFNAV", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundSuspension(TEJBaseAdapter):
    name = "tej.offshore_fund_suspension"
    version = "v1"
    description = "查詢境外基金暫停計價紀錄"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFSUSP", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOffshoreFundPerformance(TEJBaseAdapter):
    name = "tej.offshore_fund_performance"
    version = "v1"
    description = "查詢境外基金績效"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "基金代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOFUNDS", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJIFRSAccountDescriptions(TEJBaseAdapter):
    name = "tej.ifrs_account_descriptions"
    version = "v1"
    description = "查詢 IFRS 財務會計科目說明"

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
        filters = {}
        if kwargs.get("code"):
            filters["code"] = kwargs.get("code")
        return self._execute_query("TRAIL", "TAIACC", params=kwargs, filters=filters)

class TEJFinancialCoverCumulative(TEJBaseAdapter):
    name = "tej.financial_cover_cumulative"
    version = "v1"
    description = "查詢 IFRS 合併累計報表封面資料"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAIM1AA", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "公司代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAIM1AQ", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJFinancialCoverQuarterly(TEJBaseAdapter):
    name = "tej.financial_cover_quarterly"
    version = "v1"
    description = "查詢 IFRS 合併單季報表封面資料"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "公司代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAIM1AQA", params=kwargs, filters={"coid": kwargs.get("coid")})

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
                "coid": {"type": "string", "description": "期貨代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAFUTR", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOptionsBasicInfo(TEJBaseAdapter):
    name = "tej.options_basic_info"
    version = "v1"
    description = "查詢選擇權基本資料"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "選擇權代碼"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOPBAS", params=kwargs, filters={"coid": kwargs.get("coid")})

class TEJOptionsDailyTrading(TEJBaseAdapter):
    name = "tej.options_daily_trading"
    version = "v1"
    description = "查詢選擇權日交易狀況"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "coid": {"type": "string", "description": "選擇權代碼"},
                "start_date": {"type": "string", "description": "開始日期"},
                "end_date": {"type": "string", "description": "結束日期"},
            },
            "required": ["coid"]
        }

    def invoke(self, **kwargs) -> ToolResult:
        return self._execute_query("TRAIL", "TAOPTION", params=kwargs, filters={"coid": kwargs.get("coid")})

