from typing import Dict, Any
from adapters.tool_adapter import ToolAdapter
from api.database import SessionLocal
from api import financial_models
from sqlalchemy import or_

class DatabaseToolBase(ToolAdapter):
    def get_db(self):
        return SessionLocal()

class SearchCompany(DatabaseToolBase):
    name = "internal.search_company"
    version = "v1"
    description = "內部公司資料庫搜尋。支援以公司名稱或代碼 (Ticker/ID) 進行模糊搜尋。返回公司基本資料、產業分類與市值資訊。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜尋關鍵字 (支援公司名稱、股票代碼、統編)"},
                "q": {"type": "string", "description": "query 的別名"},
                "keyword": {"type": "string", "description": "query 的別名"},
                "limit": {"type": "integer", "default": 20, "description": "返回結果數量上限"}
            },
            "required": []
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        # Support aliases
        query = kwargs.get("query") or kwargs.get("q") or kwargs.get("keyword") or kwargs.get("name") or kwargs.get("code")
        limit = kwargs.get("limit", 20)
        
        if not query:
            return {"error": "Missing required parameter: query (or q/keyword/name)"}

        db = self.get_db()
        try:
            results = db.query(financial_models.Company).filter(
                or_(
                    financial_models.Company.company_name.like(f"%{query}%"),
                    financial_models.Company.ticker_symbol.like(f"%{query}%"),
                    financial_models.Company.company_id == query
                )
            ).limit(limit).all()
            
            data = []
            for r in results:
                data.append({
                    "id": r.company_id,
                    "name": r.company_name,
                    "ticker": r.ticker_symbol,
                    "sector": r.industry_sector,
                    "group": r.industry_group, # Stream (Up/Mid/Down)
                    "sub_industry": r.sub_industry,
                    "market_cap": float(r.market_cap) if r.market_cap else None
                })
            
            # Add guidance for agents to encourage using available data tools
            hint = "💡 搜尋完成（已顯示前 20 筆）。請務必使用結果中的 'id' (或 'ticker')，進一步調用 `tej.stock_price` 或 `tej.financial_summary` 等工具來獲取具體數據。單純的公司列表不足以支持辯論。"
            return {"results": data, "system_hint": hint}
        finally:
            db.close()

class GetCompanyDetails(DatabaseToolBase):
    name = "internal.get_company_details"
    version = "v1"
    description = "獲取特定公司的詳細檔案。包含財務概況、風險指標、產業地位與基本面數據。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "公司唯一識別碼 (Primary Key)"},
                "id": {"type": "string", "description": "company_id 的別名"},
                "coid": {"type": "string", "description": "company_id 的別名 (TEJ 風格)"}
            },
            "required": []
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        # Support aliases
        company_id = kwargs.get("company_id") or kwargs.get("id") or kwargs.get("coid")
        
        if not company_id:
            return {"error": "Missing required parameter: company_id (or id/coid)"}

        db = self.get_db()
        try:
            # 1. Try exact match on company_id
            company = db.query(financial_models.Company).filter(financial_models.Company.company_id == company_id).first()
            
            # 2. Try adding .TW suffix if not found and not present
            if not company and not company_id.endswith(".TW"):
                company = db.query(financial_models.Company).filter(financial_models.Company.company_id == f"{company_id}.TW").first()
                
            # 3. Try matching ticker_symbol
            if not company:
                company = db.query(financial_models.Company).filter(financial_models.Company.ticker_symbol == company_id).first()
                
            if not company:
                return {"error": f"Company not found with ID: {company_id}"}
            
            # Serialize simple object
            data = {c.name: getattr(company, c.name) for c in company.__table__.columns}
            # Handle decimals/dates for JSON serialization
            for k, v in data.items():
                if hasattr(v, 'isoformat'):
                    data[k] = v.isoformat()
                elif str(type(v)) == "<class 'decimal.Decimal'>":
                    data[k] = float(v)
            return {"data": data}
        finally:
            db.close()

class GetSecurityDetails(DatabaseToolBase):
    name = "internal.get_security_details"
    version = "v1"
    description = "獲取特定證券 (股票/債券/ETF) 的詳細規格與發行資訊。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "證券代碼 (Ticker)"}
            },
            "required": ["ticker"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        ticker = kwargs.get("ticker")
        db = self.get_db()
        try:
            security = db.query(financial_models.Security).filter(financial_models.Security.ticker == ticker).first()
            if not security:
                return {"error": "Security not found"}
            
            data = {c.name: getattr(security, c.name) for c in security.__table__.columns}
             # Handle decimals/dates for JSON serialization
            for k, v in data.items():
                if hasattr(v, 'isoformat'):
                    data[k] = v.isoformat()
                elif str(type(v)) == "<class 'decimal.Decimal'>":
                    data[k] = float(v)
            return {"data": data}
        finally:
            db.close()
