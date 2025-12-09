"""
Full Migration Script for TEJ Tools to OpenAPI Specification.
Migrates all ~25 TEJ tools from adapters/tej_adapter.py to the database with full OpenAPI specs.
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from api.database import SessionLocal
from api import models
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_tej_full():
    """Migrate all TEJ tools to database with OpenAPI specs."""
    db = SessionLocal()
    
    try:
        # Define tool metadata
        # Types: 
        # - 'basic': coid only
        # - 'time_series': coid, start_date, end_date
        # - 'special_account': code (optional)
        
        tools_metadata = [
            {
                "name": "tej.company_info",
                "table": "AIND",
                "description": "查詢台灣上市櫃公司基本資料（公司名稱、產業別、上市日期、董事長、總經理、實收資本額等）",
                "type": "basic"
            },
            {
                "name": "tej.stock_price",
                "table": "TAPRCD",
                "description": "查詢台灣股票歷史價格資料（開盤價、收盤價、成交量、報酬率、本益比、股價淨值比等）",
                "type": "time_series"
            },
            {
                "name": "tej.monthly_revenue",
                "table": "TASALE",
                "description": "查詢上市櫃月營收盈餘資料（單月營收、累計營收、月增率、年增率等）",
                "type": "time_series"
            },
            {
                "name": "tej.institutional_holdings",
                "table": "TATINST1",
                "description": "查詢三大法人買賣超資料（外資、投信、自營商買賣超張數）",
                "type": "time_series"
            },
            {
                "name": "tej.margin_trading",
                "table": "TAGIN",
                "description": "查詢融資融券資料（融資買賣、融券買賣、資券相抵等）",
                "type": "time_series"
            },
            {
                "name": "tej.foreign_holdings",
                "table": "TAQFII",
                "description": "查詢外資法人持股資料（外資持股數、持股率、可投資餘額等）",
                "type": "time_series"
            },
            {
                "name": "tej.financial_summary",
                "table": "TAIM1A",
                "description": "查詢 IFRS 以合併為主簡表累計資料（營收、毛利、營業利益、EPS、ROE、ROA等）",
                "type": "time_series"
            },
            {
                "name": "tej.fund_nav",
                "table": "TANAV",
                "description": "查詢基金淨值日資料（基金淨值、累計報酬率、規模等）",
                "type": "time_series"
            },
            {
                "name": "tej.shareholder_meeting",
                "table": "TAMT",
                "description": "查詢股東會事項資料（股東會日期、股利分派、除權息日期等）",
                "type": "time_series"
            },
            {
                "name": "tej.fund_basic_info",
                "table": "TAATT",
                "description": "查詢基金基本資料（基金名稱、類型、成立日、計價幣別等）",
                "type": "basic"
            },
            {
                "name": "tej.offshore_fund_info",
                "table": "TAOFATT",
                "description": "查詢境外基金基本資料",
                "type": "basic"
            },
            {
                "name": "tej.offshore_fund_dividend",
                "table": "TAOFCAN",
                "description": "查詢境外基金股息配發紀錄",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_holdings_region",
                "table": "TAOFIVA",
                "description": "查詢境外基金持股狀況-區域分佈",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_holdings_industry",
                "table": "TAOFIVP",
                "description": "查詢境外基金持股狀況-產業分佈",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_nav_rank",
                "table": "TAOFMNV",
                "description": "查詢境外基金淨值及月排名資料",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_nav_daily",
                "table": "TAOFNAV",
                "description": "查詢境外基金每日淨值資料",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_suspension",
                "table": "TAOFSUSP",
                "description": "查詢境外基金暫停計價紀錄",
                "type": "time_series"
            },
            {
                "name": "tej.offshore_fund_performance",
                "table": "TAOFUNDS",
                "description": "查詢境外基金績效表現",
                "type": "time_series"
            },
            {
                "name": "tej.ifrs_account_descriptions",
                "table": "TAIACC",
                "description": "查詢 IFRS 財務會計科目說明",
                "type": "special_account"
            },
            {
                "name": "tej.financial_cover_cumulative",
                "table": "TAIM1AA",
                "description": "查詢 IFRS 合併累計報表封面資料",
                "type": "time_series"
            },
            {
                "name": "tej.financial_summary_quarterly",
                "table": "TAIM1AQ",
                "description": "查詢 IFRS 合併單季簡表資料（單季營收、單季EPS等）",
                "type": "time_series"
            },
            {
                "name": "tej.financial_cover_quarterly",
                "table": "TAIM1AQA",
                "description": "查詢 IFRS 合併單季報表封面資料",
                "type": "time_series"
            },
            {
                "name": "tej.futures_data",
                "table": "TAFUTR",
                "description": "查詢期貨資料庫（開高低收、成交量、未平倉量）",
                "type": "time_series"
            },
            {
                "name": "tej.options_basic_info",
                "table": "TAOPBAS",
                "description": "查詢選擇權基本資料",
                "type": "basic"
            },
            {
                "name": "tej.options_daily_trading",
                "table": "TAOPTION",
                "description": "查詢選擇權日交易狀況",
                "type": "time_series"
            }
        ]
        
        for tool_meta in tools_metadata:
            logger.info(f"Processing {tool_meta['name']}...")
            
            # Common components
            base_url = "https://api.tej.com.tw/api/datatables"
            path = f"/TRAIL/{tool_meta['table']}.json"
            
            # Build Parameters and Schema based on type
            parameters = []
            json_schema_props = {}
            json_schema_required = []
            
            # 1. COID / Code Parameter
            if tool_meta['type'] == 'special_account':
                parameters.append({
                    "name": "code",
                    "in": "query",
                    "description": "科目代碼 (Optional)",
                    "required": False,
                    "schema": {"type": "string"}
                })
                json_schema_props["code"] = {"type": "string", "description": "科目代碼 (Optional)"}
            else:
                parameters.append({
                    "name": "coid",
                    "in": "query",
                    "description": "公司/基金/商品代碼",
                    "required": True,
                    "schema": {"type": "string"}
                })
                json_schema_props["coid"] = {"type": "string", "description": "公司/基金/商品代碼"}
                json_schema_required.append("coid")
            
            # 2. Date Parameters (for time_series)
            if tool_meta['type'] == 'time_series':
                parameters.extend([
                    {
                        "name": "mdate.gte",
                        "in": "query",
                        "description": "開始日期（格式：YYYY-MM-DD）",
                        "schema": {"type": "string", "format": "date"}
                    },
                    {
                        "name": "mdate.lte",
                        "in": "query",
                        "description": "結束日期（格式：YYYY-MM-DD）",
                        "schema": {"type": "string", "format": "date"}
                    }
                ])
                json_schema_props["start_date"] = {"type": "string", "description": "開始日期（YYYY-MM-DD）"}
                json_schema_props["end_date"] = {"type": "string", "description": "結束日期（YYYY-MM-DD）"}
            
            # 3. Pagination Parameters (All TEJ tools support this)
            parameters.extend([
                {
                    "name": "opts.limit",
                    "in": "query",
                    "description": "返回結果數量限制",
                    "schema": {"type": "integer", "default": 50}
                },
                {
                    "name": "opts.offset",
                    "in": "query",
                    "description": "結果偏移量（分頁）",
                    "schema": {"type": "integer", "default": 0}
                }
            ])
            # Add opts.limit to json_schema as well, as it's often useful for the agent to control
            json_schema_props["opts.limit"] = {
                "type": "integer", 
                "description": "返回結果數量 (TEJ API parameter)", 
                "default": 50
            }

            # Build Full OpenAPI Spec
            openapi_spec = {
                "openapi": "3.0.0",
                "info": {
                    "title": tool_meta['name'].replace('.', ' ').title(),
                    "version": "1.0.0",
                    "description": tool_meta['description']
                },
                "servers": [{"url": base_url}],
                "paths": {
                    path: {
                        "get": {
                            "summary": tool_meta['description'],
                            "operationId": f"get_{tool_meta['table']}",
                            "description": tool_meta['description'],
                            "parameters": parameters,
                            "responses": {
                                "200": {
                                    "description": "成功返回資料",
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {
                                                    "data": {
                                                        "type": "array",
                                                        "items": {"type": "object"}
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
                "security": [{"ApiKeyAuth": []}]
            }

            # Build Tool Object
            tool_obj = models.Tool(
                name=tool_meta['name'],
                version="v1",
                description=tool_meta['description'],
                type="api",
                provider="tej",
                base_url=base_url,
                auth_type="api_key",
                auth_config={"in": "query", "param": "api_key"},
                rate_limit={"tps": 5, "burst": 10},
                cache_ttl=21600,  # 6 hours
                timeout=15,
                openapi_spec=openapi_spec,
                json_schema={
                    "type": "object",
                    "properties": json_schema_props,
                    "required": json_schema_required
                },
                group="tej",
                enabled=True
            )

            # Upsert into DB
            existing_tool = db.query(models.Tool).filter(models.Tool.name == tool_meta['name']).first()
            if existing_tool:
                logger.info(f"Updating existing tool: {tool_meta['name']}")
                for key, value in tool_obj.__dict__.items():
                    if not key.startswith('_') and key != 'id': # Don't overwrite ID
                        setattr(existing_tool, key, value)
            else:
                logger.info(f"Creating new tool: {tool_meta['name']}")
                db.add(tool_obj)
        
        db.commit()
        logger.info("\n🎉 Full TEJ migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_tej_full()