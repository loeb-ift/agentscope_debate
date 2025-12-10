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
    description = "從內部資料庫搜尋公司資料。可使用名稱或代碼。返回公司 ID、名稱、Ticker、產業別與市值。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜尋關鍵字 (名稱、代碼)"},
                "limit": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("query")
        limit = kwargs.get("limit", 5)
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
                    "market_cap": float(r.market_cap) if r.market_cap else None
                })
            return {"results": data}
        finally:
            db.close()

class GetCompanyDetails(DatabaseToolBase):
    name = "internal.get_company_details"
    version = "v1"
    description = "獲取公司詳細資料，包括財務概況與風險指標。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "公司 ID (Primary)"},
                "id": {"type": "string", "description": "Alias for company_id"},
                "coid": {"type": "string", "description": "Alias for company_id (TEJ style)"}
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
            company = db.query(financial_models.Company).filter(financial_models.Company.company_id == company_id).first()
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
    description = "獲取證券詳細資料 (Stock/Bond/ETF)。"

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
