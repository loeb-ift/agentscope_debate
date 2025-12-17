from typing import Dict, Any
from adapters.tool_adapter import ToolAdapter
from api.database import SessionLocal
from api import financial_models
from sqlalchemy import or_

class InternalTermLookup(ToolAdapter):
    name = "internal.term.lookup"
    version = "v1"
    description = """查詢內部金融術語知識庫。
    **使用時機**: 當遇到不確定的財經專有名詞，或辯論雙方對定義有歧義時使用。
    **功能**: 支援模糊搜尋、分類篩選。返回標準定義、計算公式與別名。"""

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "搜尋關鍵字 (支援術語名稱、別名或定義內容)"},
                "category": {"type": "string", "description": "分類篩選 (如 'Valuation', 'Risk', 'Macro')"},
                "lang": {"type": "string", "description": "語言代碼 (預設 'zh-TW')"},
                "limit": {"type": "integer", "default": 20, "description": "返回結果數量上限"}
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
    description = "獲取特定金融術語的完整解釋，包含詳細定義、計算公式、備註與關聯資訊。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "term_id": {"type": "string", "description": "術語唯一識別碼 (Term ID)"},
                "name": {"type": "string", "description": "術語名稱 (精確匹配)"}
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
