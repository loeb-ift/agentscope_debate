from typing import Dict, Any, List
from adapters.tool_adapter import ToolAdapter
from api.database import SessionLocal
from api import financial_models
from sqlalchemy import or_

class GetIndustryTree(ToolAdapter):
    name = "internal.get_industry_tree"
    version = "v1"
    description = "獲取產業鏈結構圖。可查詢特定產業 (Sector) 的上下游關係與成分股。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sector": {"type": "string", "description": "產業類別 (如 '半導體', '航運')。若留空則返回所有產業清單。"}
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
        sector = kwargs.get("sector")
        db = SessionLocal()
        try:
            # 簡單實作：從 Company 表聚合
            # 理想情況應讀取快取或專用表，這裡為求即時性直接查詢
            query = db.query(financial_models.Company)
            if sector:
                query = query.filter(financial_models.Company.industry_sector == sector)
            
            companies = query.all()
            
            # Group by Stream (Group) -> Sub-industry
            tree = {}
            for c in companies:
                sec = c.industry_sector or "未分類"
                groups = (c.industry_group or "未分類").split(';')
                
                if sec not in tree: tree[sec] = {}
                
                for g in groups:
                    g = g.strip()
                    if not g: continue
                    if g not in tree[sec]: tree[sec][g] = []
                    
                    tree[sec][g].append({
                        "id": c.company_id,
                        "name": c.company_name,
                        "sub_industry": c.sub_industry
                    })
            
            return {"tree": tree}
        finally:
            db.close()

class GetKeyPersonnel(ToolAdapter):
    name = "internal.get_key_personnel"
    version = "v1"
    description = "獲取公司的董監事與經理人名單。用於分析管理層背景與公司治理。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "公司 ID (如 '2330', '2330.TW')"}
            },
            "required": ["company_id"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        company_id = kwargs.get("company_id")
        if not company_id: return {"error": "Missing company_id"}
        
        db = SessionLocal()
        try:
            # Auto-fix .TW suffix
            targets = [company_id]
            if not company_id.endswith(".TW"): targets.append(f"{company_id}.TW")
            if company_id.endswith(".TW"): targets.append(company_id.replace(".TW", ""))
            
            personnel = db.query(financial_models.KeyPersonnel).filter(
                financial_models.KeyPersonnel.company_id.in_(targets)
            ).all()
            
            results = []
            for p in personnel:
                results.append({
                    "name": p.full_name,
                    "title": p.position_title,
                    "type": p.position_type
                })
            
            if not results:
                return {"message": "No personnel data found", "data": []}
                
            return {"data": results}
        finally:
            db.close()

class GetCorporateRelationships(ToolAdapter):
    name = "internal.get_corporate_relationships"
    version = "v1"
    description = "獲取公司的關係企業與轉投資結構。用於分析集團版圖。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "company_id": {"type": "string", "description": "公司 ID"}
            },
            "required": ["company_id"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        company_id = kwargs.get("company_id")
        if not company_id: return {"error": "Missing company_id"}
        
        db = SessionLocal()
        try:
            targets = [company_id]
            if not company_id.endswith(".TW"): targets.append(f"{company_id}.TW")
            
            # Query relationships where this company is either side 1 or 2
            rels = db.query(financial_models.CorporateRelationship).filter(
                or_(
                    financial_models.CorporateRelationship.company_id_1.in_(targets),
                    financial_models.CorporateRelationship.company_id_2.in_(targets)
                )
            ).all()
            
            results = []
            for r in rels:
                # Determine role
                is_c1 = r.company_id_1 in targets
                target = r.company_id_2 if is_c1 else r.company_id_1
                
                results.append({
                    "target_company": target,
                    "relationship": r.relationship_type,
                    "description": r.description
                })
                
            return {"data": results}
        finally:
            db.close()
