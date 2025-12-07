from typing import Dict, Any
from adapters.tool_adapter import ToolAdapter
from api.database import SessionLocal
from api import financial_models
from sqlalchemy import or_

class InternalTermLookup(ToolAdapter):
    name = "internal.term.lookup"
    version = "v1"
    description = "查詢內部金融術語：支援關鍵字、分類與語言過濾，返回定義、別名與標籤。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "關鍵字（名稱/別名/定義內文）"},
                "category": {"type": "string", "description": "分類過濾"},
                "lang": {"type": "string", "description": "語言，預設 zh-TW"},
                "limit": {"type": "integer", "default": 20}
            },
            "required": ["q"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        q = kwargs.get("q", "").strip()
        category = kwargs.get("category")
        lang = kwargs.get("lang", "zh-TW")
        limit = kwargs.get("limit", 20)

        db = SessionLocal()
        try:
            query = db.query(financial_models.FinancialTerm)
            if q:
                like = f"%{q}%"
                query = query.filter(or_(
                    financial_models.FinancialTerm.term_name.like(like),
                    financial_models.FinancialTerm.definition.like(like)
                ))
            if category:
                query = query.filter(financial_models.FinancialTerm.term_category == category)

            results = query.limit(limit).all()
            data = []
            for t in results:
                meta = getattr(t, 'meta', None) or {}
                lang_ok = (not lang) or (meta.get('lang') in (None, lang))
                if not lang_ok:
                    continue
                data.append({
                    "id": t.term_id,
                    "name": t.term_name,
                    "category": t.term_category,
                    "definition": t.definition,
                    "aliases": meta.get('aliases'),
                    "tags": meta.get('tags'),
                    "lang": meta.get('lang'),
                    "version": meta.get('version'),
                    "formula": meta.get('formula'),
                    "notes": meta.get('notes')
                })
            return {"results": data}
        finally:
            db.close()

class InternalTermExplain(ToolAdapter):
    name = "internal.term.explain"
    version = "v1"
    description = "根據 term_id 或名稱返回完整定義，包含公式與備註。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "term_id": {"type": "string"},
                "name": {"type": "string"}
            },
            "oneOf": [
                {"required": ["term_id"]},
                {"required": ["name"]}
            ]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        term_id = kwargs.get("term_id")
        name = kwargs.get("name")
        db = SessionLocal()
        try:
            obj = None
            if term_id:
                obj = db.query(financial_models.FinancialTerm).filter(financial_models.FinancialTerm.term_id == term_id).first()
            elif name:
                obj = db.query(financial_models.FinancialTerm).filter(financial_models.FinancialTerm.term_name == name).first()
            if not obj:
                return {"error": "Term not found"}
            meta = getattr(obj, 'meta', None) or {}
            return {
                "id": obj.term_id,
                "name": obj.term_name,
                "category": obj.term_category,
                "definition": obj.definition,
                "aliases": meta.get('aliases'),
                "tags": meta.get('tags'),
                "lang": meta.get('lang'),
                "version": meta.get('version'),
                "formula": meta.get('formula'),
                "notes": meta.get('notes')
            }
        finally:
            db.close()
