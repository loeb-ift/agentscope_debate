
from api.database import SessionLocal
from api import models
import json

def update_toolsets_and_links():
    db = SessionLocal()
    try:
        # 1. Define ToolSet Requirements
        toolset_defs = {
            "Quantitative ToolSet": {
                "desc": "量化分析工具集：優先使用內部數據 (ChinaTimes) 與驗證報價，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.stock_rt", "chinatimes.stock_kline", "chinatimes.market_index", 
                    "chinatimes.market_rankings", "financial.technical_analysis", 
                    "financial.get_verified_price", "twse.stock_day", "financial.pdr_reader", 
                    "ods.eda_describe", "av.GLOBAL_QUOTE", "av.TIME_SERIES_DAILY", 
                    "yfinance.stock_price", "search.smart", "searxng.search",
                    "tej.stock_price", "tej.futures_data", "tej.options_daily_trading"
                ]
            },
            "Valuation ToolSet": {
                "desc": "估值建模工具集：優先使用內部基本面數據 (ChinaTimes) 與官方工具，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.stock_fundamental", "chinatimes.balance_sheet", "chinatimes.income_statement", 
                    "chinatimes.cash_flow", "ods.eda_describe", "search.smart", "searxng.search",
                    "tej.financial_summary", "tej.financial_summary_quarterly", "tej.shareholder_meeting"
                ]
            },
            "Industry ToolSet": {
                "desc": "產業研究工具集：優先內部產業分析 (ChinaTimes) 與結構工具，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.sector_info", "chinatimes.stock_fundamental", 
                    "internal.get_industry_tree", "internal.get_company_details", "internal.search_company",
                    "browser.browse", "search.smart", "searxng.search", "ods.eda_describe",
                    "tej.company_info", "tej.monthly_revenue"
                ]
            },
            "Risk ToolSet": {
                "desc": "風控籌碼工具集：優先使用內部即時新聞與事實 (ChinaTimes)，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.stock_news", "news.search_chinatimes", "chinatimes.financial_ratios", 
                    "chinatimes.stock_fundamental", "browser.browse", "search.smart", "searxng.search",
                    "ods.eda_describe", "tej.institutional_holdings", "tej.margin_trading"
                ]
            },
            "Strategic ToolSet": {
                "desc": "核心策略與報告工具集：完整內部權限 (ChinaTimes) 與全球宏觀工具，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.market_index", "chinatimes.balance_sheet", "chinatimes.income_statement", 
                    "chinatimes.cash_flow", "chinatimes.financial_ratios", "chinatimes.stock_news",
                    "news.search_chinatimes", "chairman.eda_analysis", "ods.eda_describe", 
                    "financial.technical_analysis", "financial.get_verified_price", "financial.pdr_reader", 
                    "av.CPI", "av.FEDERAL_FUNDS_RATE", "av.TREASURY_YIELD", "av.INFLATION", 
                    "browser.browse", "search.smart", "searxng.search", 
                    "internal.get_industry_tree", "internal.get_key_personnel", "internal.get_corporate_relationships",
                    "tej.company_info", "tej.financial_summary"
                ]
            },
            "Growth ToolSet": {
                "desc": "成長動能工具集：優先內部排行 (ChinaTimes) 與趨勢分析，TEJ 僅作備援。",
                "tools": [
                    "chinatimes.market_rankings", "chinatimes.sector_info", "chinatimes.stock_rt",
                    "financial.technical_analysis", "av.GLOBAL_QUOTE", "av.TOP_GAINERS_LOSERS", 
                    "search.smart", "searxng.search", "ods.eda_describe"
                ]
            }
        }

        # 2. Update/Create ToolSets
        ts_id_map = {}
        for name, data in toolset_defs.items():
            ts = db.query(models.ToolSet).filter(models.ToolSet.name == name).first()
            
            if not ts:
                ts = models.ToolSet(name=name, description=data["desc"], tool_names=data["tools"])
                db.add(ts)
                db.flush()
                print(f"Created ToolSet: {name}")
            else:
                ts.description = data["desc"]
                ts.tool_names = data["tools"]
                print(f"Updated ToolSet: {name}")
            ts_id_map[name] = ts.id

        db.commit()

        # 3. Define Agent-ToolSet Mappings
        agent_mapping = {
            "量化分析師": "Quantitative ToolSet",
            "市場交易員": "Quantitative ToolSet",
            "價值投資人": "Valuation ToolSet",
            "風控官": "Risk ToolSet",
            "挑戰者": "Risk ToolSet",
            "供應鏈偵探": "Industry ToolSet",
            "宏觀策略師": "Strategic ToolSet",
            "Chairman": "Strategic ToolSet",
            "首席投資策略師 (Chief Investment Strategist)": "Strategic ToolSet",
            "Investment Report Editor": "Strategic ToolSet",
            "成長策略師": "Growth ToolSet",
            "Jury": "Strategic ToolSet",
            "合規哨兵": "Strategic ToolSet"
        }

        # 4. Apply Mappings
        for agent_name, ts_name in agent_mapping.items():
            agent = db.query(models.Agent).filter(models.Agent.name.like(f"%{agent_name}%")).first()
            if not agent:
                print(f"Agent not found: {agent_name}")
                continue
            
            ts_id = ts_id_map.get(ts_name)
            if not ts_id: continue

            # Clear existing and add new
            db.query(models.AgentToolSet).filter(models.AgentToolSet.agent_id == agent.id).delete()
            link = models.AgentToolSet(agent_id=agent.id, toolset_id=ts_id)
            db.add(link)
            print(f"Linked Agent '{agent.name}' to ToolSet '{ts_name}'")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_toolsets_and_links()
