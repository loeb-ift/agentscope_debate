"""
POC: 遷移 2 個 TEJ 工具到 OpenAPI 規範
- tej.company_info
- tej.stock_price
"""
import sys
sys.path.insert(0, '/app')

from api.database import SessionLocal
from api import models

def migrate_tej_poc_tools():
    """遷移 TEJ Company Info 和 Stock Price 作為 POC"""
    db = SessionLocal()
    
    try:
        # 1. TEJ Company Info
        company_info_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "TEJ Company Info",
                "version": "1.0.0",
                "description": "查詢台灣上市櫃公司基本資料（公司名稱、產業別、上市日期等）"
            },
            "servers": [
                {
                    "url": "https://api.tej.com.tw/api/datatables"
                }
            ],
            "paths": {
                "/TRAIL/TAIACC.json": {
                    "get": {
                        "summary": "取得公司基本資料",
                        "operationId": "getCompanyInfo",
                        "description": "根據公司代碼查詢公司基本資訊",
                        "parameters": [
                            {
                                "name": "coid",
                                "in": "query",
                                "description": "公司代碼（如 2330 代表台積電）",
                                "required": True,
                                "schema": {
                                    "type": "string"
                                }
                            },
                            {
                                "name": "opts.limit",
                                "in": "query",
                                "description": "返回結果數量限制",
                                "schema": {
                                    "type": "integer",
                                    "default": 50
                                }
                            },
                            {
                                "name": "opts.offset",
                                "in": "query",
                                "description": "結果偏移量（分頁）",
                                "schema": {
                                    "type": "integer",
                                    "default": 0
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "成功返回公司資料",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "data": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_key"
                    }
                }
            },
            "security": [
                {
                    "ApiKeyAuth": []
                }
            ]
        }
        
        company_info_tool = models.Tool(
            name="tej.company_info",
            version="v1",
            description="查詢台灣上市櫃公司基本資料（公司名稱、產業別、上市日期等）",
            type="api",
            provider="tej",
            base_url="https://api.tej.com.tw/api/datatables",
            auth_type="api_key",
            auth_config={"in": "query", "param": "api_key"},
            rate_limit={"tps": 5, "burst": 10},
            cache_ttl=21600,  # 6 hours
            timeout=15,
            openapi_spec=company_info_spec,
            json_schema={
                "type": "object",
                "properties": {
                    "coid": {
                        "type": "string",
                        "description": "公司代碼（如 2330）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回結果數量",
                        "default": 50
                    }
                },
                "required": ["coid"]
            },
            group="tej",
            enabled=True
        )
        
        # 2. TEJ Stock Price
        stock_price_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "TEJ Stock Price",
                "version": "1.0.0",
                "description": "查詢台灣股票歷史價格資料"
            },
            "servers": [
                {
                    "url": "https://api.tej.com.tw/api/datatables"
                }
            ],
            "paths": {
                "/TWN/APRCD.json": {
                    "get": {
                        "summary": "取得股票價格資料",
                        "operationId": "getStockPrice",
                        "description": "查詢指定股票的歷史價格資料",
                        "parameters": [
                            {
                                "name": "coid",
                                "in": "query",
                                "description": "公司代碼（如 2330）",
                                "required": True,
                                "schema": {
                                    "type": "string"
                                }
                            },
                            {
                                "name": "mdate.gte",
                                "in": "query",
                                "description": "開始日期（格式：YYYY-MM-DD）",
                                "schema": {
                                    "type": "string",
                                    "format": "date"
                                }
                            },
                            {
                                "name": "mdate.lte",
                                "in": "query",
                                "description": "結束日期（格式：YYYY-MM-DD）",
                                "schema": {
                                    "type": "string",
                                    "format": "date"
                                }
                            },
                            {
                                "name": "opts.limit",
                                "in": "query",
                                "description": "返回結果數量限制",
                                "schema": {
                                    "type": "integer",
                                    "default": 50
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "成功返回股價資料",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "data": {
                                                    "type": "array"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_key"
                    }
                }
            },
            "security": [
                {
                    "ApiKeyAuth": []
                }
            ]
        }
        
        stock_price_tool = models.Tool(
            name="tej.stock_price",
            version="v1",
            description="查詢台灣股票歷史價格資料（開盤價、收盤價、成交量等）",
            type="api",
            provider="tej",
            base_url="https://api.tej.com.tw/api/datatables",
            auth_type="api_key",
            auth_config={"in": "query", "param": "api_key"},
            rate_limit={"tps": 5, "burst": 10},
            cache_ttl=21600,  # 6 hours
            timeout=15,
            openapi_spec=stock_price_spec,
            json_schema={
                "type": "object",
                "properties": {
                    "coid": {
                        "type": "string",
                        "description": "公司代碼（如 2330）"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "開始日期（YYYY-MM-DD）"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "結束日期（YYYY-MM-DD）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回結果數量",
                        "default": 50
                    }
                },
                "required": ["coid"]
            },
            group="tej",
            enabled=True
        )
        
        # 檢查是否已存在
        existing_company = db.query(models.Tool).filter(models.Tool.name == "tej.company_info").first()
        existing_price = db.query(models.Tool).filter(models.Tool.name == "tej.stock_price").first()
        
        if existing_company:
            print("⚠️  tej.company_info already exists, updating...")
            for key, value in company_info_tool.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing_company, key, value)
        else:
            db.add(company_info_tool)
            print("✅ Added tej.company_info")
        
        if existing_price:
            print("⚠️  tej.stock_price already exists, updating...")
            for key, value in stock_price_tool.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing_price, key, value)
        else:
            db.add(stock_price_tool)
            print("✅ Added tej.stock_price")
        
        db.commit()
        print("\n🎉 POC migration completed!")
        print("📋 Migrated tools:")
        print("  1. tej.company_info - 查詢公司基本資料")
        print("  2. tej.stock_price - 查詢股票價格")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_tej_poc_tools()
