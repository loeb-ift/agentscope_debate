from sqlalchemy.orm import Session
from api import models
from api.prompt_service import PromptService
from api.toolset_service import ToolSetService
from api.tool_registry import tool_registry
from adapters.http_tool_adapter import HTTPToolAdapter
from adapters.database_tool_adapter import SearchCompany, GetCompanyDetails, GetSecurityDetails
import yaml
import os
import glob
from api.financial_terms_data import FINANCIAL_TERMS_DATA
from api import financial_models
import json
from api.config import Config

PROMPTS_AGENTS_DIR = "prompts/agents"

def initialize_financial_terms(db: Session):
    """初始化金融術語對照表（從內建資料與 JSON 種子檔），支持增量更新"""
    print("Initializing financial terms...")

    # Load existing terms into a dictionary for quick lookup
    existing_terms = {t.term_id: t for t in db.query(financial_models.FinancialTerm).all()}
    terms_to_save = []

    # 1) 先載入 data/seeds/financial_terms.zh-TW.json（若存在）
    seed_path = os.path.join("data", "seeds", "financial_terms.zh-TW.json")
    if os.path.exists(seed_path):
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed = json.load(f)
                for item in seed.get("terms", []):
                    term_id = item.get("id")
                    zh_name = item.get("name")
                    category = item.get("category")
                    definition = item.get("definition")
                    meta = {
                        "aliases": item.get("aliases"),
                        "tags": item.get("tags"),
                        "lang": item.get("lang"),
                        "version": item.get("version"),
                        "formula": item.get("formula"),
                        "notes": item.get("notes")
                    }
                    if not term_id:
                        term_id = f"{category}_{zh_name}".lower().replace(" ", "_")[:50]
                    
                    if term_id in existing_terms:
                        # Update existing term
                        existing_term = existing_terms[term_id]
                        existing_term.term_name = zh_name
                        existing_term.term_category = category
                        existing_term.definition = definition
                        existing_term.meta = meta
                        terms_to_save.append(existing_term)
                    else:
                        # Create new term
                        new_term = financial_models.FinancialTerm(
                            term_id=term_id,
                            term_name=zh_name,
                            term_category=category,
                            definition=definition,
                            meta=meta
                        )
                        terms_to_save.append(new_term)
                        existing_terms[term_id] = new_term # Add to tracking map
        except Exception as e:
            print(f"Warning: failed to load seed financial terms from JSON: {e}")

    # 2) 再補充 api/financial_terms_data.py 內建資料（避免與上面重複）
    for item in FINANCIAL_TERMS_DATA:
        term_id = None
        zh_name = None
        category = None
        definition = None
        meta = None
        
        if isinstance(item, tuple):
            zh_name, en_name, category = item
            term_id = f"{category}_{en_name}".lower().replace(" ", "_").replace(",", "").replace(".", "").replace("&", "and")[:50]
            definition = en_name
        elif isinstance(item, dict):
            term_id = item.get("id")
            zh_name = item.get("name")
            category = item.get("category")
            definition = item.get("definition")
            if not term_id:
                term_id = f"{category}_{zh_name}".lower().replace(" ", "_")[:50]
        
        # Only add if not already covered by JSON seed (or previous existing check)
        # Note: In a real merge scenario, we might want code to override DB, but let's assume JSON seed > Code > DB
        if term_id and term_id not in existing_terms:
             new_term = financial_models.FinancialTerm(
                term_id=term_id,
                term_name=zh_name,
                term_category=category,
                definition=definition,
                meta=meta
            )
             terms_to_save.append(new_term)
             existing_terms[term_id] = new_term

    # 寫入 DB
    try:
        if terms_to_save:
            # For new items, we can use bulk_save_objects, but for updates on attached objects, session.commit handles it.
            # However, since we mixed new and existing attached objects, plain commit should work if they are attached.
            # For detached objects (if any), merge would be needed.
            # Since we fetched existing_terms from this session, they are attached. New ones are transient.
            # We add new ones to session.
            for t in terms_to_save:
                db.add(t) 
            db.commit()
        print(f"Initialized/Updated {len(terms_to_save)} financial terms.")
    except Exception as e:
        print(f"Error initializing financial terms: {e}")
        db.rollback()

def initialize_toolsets(db: Session):
    """初始化預設工具集並分配給 Agent"""
    print("Initializing toolsets...")
    
    # 1. Global Standard ToolSet (Search + Yahoo Finance + Internal DB Search)
    global_tools = [
        "searxng.search",
        "duckduckgo.search",
        "yfinance.stock_info",
        "internal.search_company", # Add Internal DB tools to global
        "internal.get_company_details",
        "internal.get_security_details",
        # ChinaTimes Suite (if enabled in env, but safe to list here as registry handles availability)
        "news.search_chinatimes",
        "chinatimes.stock_rt",
        "chinatimes.stock_news",
        "chinatimes.stock_kline",
        # New ChinaTimes Tools
        "chinatimes.market_index",
        "chinatimes.market_rankings",
        "chinatimes.sector_info",
        "chinatimes.stock_fundamental",
        # EDA Tool (Chairman only by design, but registered globally to ensure visibility in UI/Testing if needed)
        # 實務上主席會使用 eda_tool_adapter，其內部會調用 ods.eda_describe
        # 這裡加入 chairman.eda_analysis 讓其成為可選工具
        "chairman.eda_analysis"
    ]
    
    global_ts = db.query(models.ToolSet).filter(models.ToolSet.is_global == True).first()
    if not global_ts:
        global_ts = models.ToolSet(
            name="Global Standard Tools",
            description="基礎搜尋、國際財經資訊與內部資料庫工具",
            tool_names=global_tools,
            is_global=True
        )
        db.add(global_ts)
    else:
        # Update existing global toolset to ensure it has new tools
        current_tools = set(global_ts.tool_names)
        updated_tools = list(current_tools | set(global_tools))
        global_ts.tool_names = updated_tools
    
    db.commit()
    db.refresh(global_ts)

    # 2. Role-Specific ToolSets
    # Updated to include ChinaTimes tools and Search for better coverage
    role_toolsets_config = {
        "Quantitative ToolSet": {
            "desc": "量化分析工具集：專注於價格數據、期貨選擇權與即時市場動能，支援量化模型運算。",
            "tools": [
                "tej.stock_price", "tej.futures_data", "tej.options_daily_trading", "tej.financial_cover_cumulative",
                "chinatimes.stock_kline", "chinatimes.market_rankings", "chinatimes.stock_rt", "chinatimes.financial_ratios",
                "finmind.data_loader", "searxng.search"
            ],
            "target_roles": ["量化分析師"]
        },
        "Valuation ToolSet": {
            "desc": "估值建模工具集：專注於財報細節、股利政策與會計準則，支援 DCF/PE/PB 估值模型。",
            "tools": [
                "tej.financial_summary", "tej.financial_summary_quarterly", "tej.shareholder_meeting", "tej.stock_price",
                "tej.ifrs_account_descriptions",
                "chinatimes.stock_fundamental", "chinatimes.balance_sheet", "chinatimes.income_statement", "chinatimes.cash_flow",
                "searxng.search"
            ],
            "target_roles": ["價值投資人"]
        },
        "Industry ToolSet": {
            "desc": "產業研究工具集：專注於月營收變化、公司基本資料與競爭者比較，支援產業鏈分析。",
            "tools": [
                "tej.monthly_revenue", "tej.company_info", "tej.financial_summary", "tej.offshore_fund_holdings_industry",
                "chinatimes.sector_info", "chinatimes.stock_fundamental", "chinatimes.market_rankings",
                "searxng.search"
            ],
            "target_roles": ["產業研究員"]
        },
        "Risk ToolSet": {
            "desc": "風控合規工具集：專注於籌碼分佈、融資券變化與外資動向，支援風險預警與合規檢查。",
            "tools": [
                "tej.institutional_holdings", "tej.margin_trading", "tej.foreign_holdings", "tej.offshore_fund_suspension",
                "chinatimes.stock_fundamental", "chinatimes.financial_ratios", "chinatimes.stock_news",
                "searxng.search"
            ],
            "target_roles": ["風控官", "挑戰者"]
        },
        "Strategic ToolSet": {
            "desc": "策略規劃與報告撰寫工具集：包含完整的財報查詢、新聞檢索與產業分析工具，支援撰寫深度投資報告。",
            "tools": [
                # TEJ Essentials
                "tej.company_info", "tej.financial_summary", "tej.stock_price", "tej.monthly_revenue",
                "tej.institutional_holdings", "tej.financial_cover_quarterly",
                # ChinaTimes Essentials
                "chinatimes.stock_fundamental", "chinatimes.market_index", "chinatimes.sector_info",
                "chinatimes.stock_rt", "chinatimes.market_rankings",
                # Financial Statements
                "chinatimes.balance_sheet", "chinatimes.income_statement",
                "chinatimes.cash_flow", "chinatimes.financial_ratios",
                # Internal & Search
                "internal.get_industry_tree", "searxng.search"
            ],
            "target_roles": ["首席分析師", "報告主筆", "宏觀策略師", "report_editor"]
        },
        "Growth ToolSet": {
            "desc": "成長動能工具集：專注於市場熱點、排行與類股輪動，支援尋找高成長標的。",
            "tools": ["chinatimes.market_rankings", "chinatimes.sector_info"],
            "target_roles": ["成長策略師", "市場交易員"]
        }
    }

    for ts_name, ts_config in role_toolsets_config.items():
        toolset = db.query(models.ToolSet).filter(models.ToolSet.name == ts_name).first()
        if not toolset:
            toolset = models.ToolSet(
                name=ts_name,
                description=ts_config["desc"],
                tool_names=ts_config["tools"],
                is_global=False
            )
            db.add(toolset)
            db.commit()
            db.refresh(toolset)
        else:
            # Update existing toolset definition (Tools & Description)
            current_tools = set(toolset.tool_names)
            new_tools = set(ts_config["tools"])
            
            updated = False
            # Check for tool updates
            if not new_tools.issubset(current_tools):
                print(f"Updating tools for toolset: {ts_name}")
                toolset.tool_names = list(current_tools | new_tools)
                updated = True
                
            # Check for description updates
            if toolset.description != ts_config["desc"]:
                print(f"Updating description for toolset: {ts_name}")
                toolset.description = ts_config["desc"]
                updated = True
                
            if updated:
                db.commit()
                db.refresh(toolset)
        
        # Assign to matching agents
        for target_role in ts_config["target_roles"]:
            # Find agents whose name OR role contains the target string
            # This ensures robust matching for both display names (e.g. "Investment Report Editor") and role IDs (e.g. "report_editor")
            agents = db.query(models.Agent).filter(
                (models.Agent.name.like(f"%{target_role}%")) |
                (models.Agent.role.like(f"%{target_role}%"))
            ).all()
            
            for agent in agents:
                # Check if already assigned
                exists = db.query(models.AgentToolSet).filter(
                    models.AgentToolSet.agent_id == agent.id,
                    models.AgentToolSet.toolset_id == toolset.id
                ).first()
                if not exists:
                    print(f"Assigning '{ts_name}' to agent '{agent.name}'")
                    db.add(models.AgentToolSet(agent_id=agent.id, toolset_id=toolset.id))
    
    db.commit()

def initialize_internal_tools(db: Session):
    """註冊內部 API 工具 (Service Adapter Pattern)"""
    # 這裡演示如何將內部 API 註冊為 HTTP 工具
    # 實際使用時，因為我們已經有了 DatabaseToolAdapter (Native)，可能不需要 HTTP 版本的 Tool
    # 但為了符合「Service Adapter」架構，我們可以註冊它們
    # 為了避免重複，這裡僅做示例，或檢查是否存在
    
    internal_base = "http://localhost:8000/api/v1/internal"
    
    tools_to_register = [
        {
            "name": "service.companies",
            "description": "Internal Company Service API",
            "url": f"{internal_base}/companies",
            "method": "GET",
            "schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}
        }
    ]
    
    for t_data in tools_to_register:
        existing = db.query(models.Tool).filter(models.Tool.name == t_data['name']).first()
        if not existing:
            print(f"Registering internal service tool: {t_data['name']}")
            new_tool = models.Tool(
                name=t_data['name'],
                type="http",
                json_schema=t_data['schema'],
                api_config={"url": t_data['url'], "method": t_data['method']},
                group="internal_services",
                enabled=True
            )
            db.add(new_tool)
            # Note: celery_app will load this into registry on restart
            
    db.commit()

def initialize_default_agents(db: Session):
    """初始化預設 Agent，從 YAML 文件加載 (支持更新)"""
    # Removed early return to allow updates/additions
    # if db.query(models.Agent).first():
    #    return

    print("Initializing default agents from files...")
    
    if not os.path.exists(PROMPTS_AGENTS_DIR):
        print(f"Warning: Agents directory not found at {PROMPTS_AGENTS_DIR}")
        return

    agent_files = glob.glob(os.path.join(PROMPTS_AGENTS_DIR, "*.yaml"))
    
    agents_created = []
    for file_path in agent_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data: continue
                
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if not item.get('name'): continue
                    
                    existing_agent = db.query(models.Agent).filter(models.Agent.name == item['name']).first()
                    if existing_agent:
                        # Update existing agent's prompt to ensure file changes are reflected
                        if existing_agent.system_prompt != item['system_prompt']:
                            print(f"Updating system prompt for agent: {item['name']}")
                            existing_agent.system_prompt = item['system_prompt']
                            agents_created.append(existing_agent) # Reuse list for commit trigger
                        continue

                    new_agent = models.Agent(
                        name=item['name'],
                        role=item['role'],
                        specialty=item.get('specialty'),
                        system_prompt=item['system_prompt'],
                        config_json=item.get('config_json', {})
                    )
                    db.add(new_agent)
                    agents_created.append(new_agent)
        except Exception as e:
            print(f"Error loading agent file {file_path}: {e}")

    if agents_created:
        try:
            db.commit()
            print(f"Created/Updated {len(agents_created)} agents from files.")
        except Exception as e:
            print(f"Error committing agents: {e}")
            db.rollback()

def initialize_default_teams(db: Session):
    """初始化3個極具特色的辯論團隊 (Teams)"""
    print("Initializing default teams...")

    teams_config = [
        {
            "name": "價值護城河 (Value Moat)",
            "description": "穩健防守，專注基本面與風險控制。成員：價值投資人、風控官、產業研究員。",
            "members": ["價值投資人", "風控官", "產業研究員"]
        },
        {
            "name": "趨勢捕手 (Trend Hunters)",
            "description": "激進進攻，捕捉成長動能與宏觀機會。成員：成長策略師、市場交易員、宏觀策略師。",
            "members": ["成長策略師", "市場交易員", "宏觀策略師"]
        },
        {
            "name": "數據決策 (Data Driven)",
            "description": "量化為王，以數據與邏輯戰勝直覺。成員：量化分析師、首席分析師、挑戰者。",
            "members": ["量化分析師", "首席分析師", "挑戰者"]
        },
        {
            "name": "逆向操作 (Contrarian Squad)",
            "description": "人棄我取，在危機中尋找被錯殺的機會。成員：挑戰者、價值投資人、宏觀策略師。",
            "members": ["挑戰者", "價值投資人", "宏觀策略師"]
        },
        {
            "name": "產業深潛 (Industry Deep Dive)",
            "description": "專注供應鏈細節與技術迭代，尋找結構性贏家。成員：產業研究員、成長策略師、量化分析師。",
            "members": ["產業研究員", "成長策略師", "量化分析師"]
        },
        {
            "name": "波動率套利 (Volatility Arbitrage)",
            "description": "利用市場恐慌與情緒波動獲利。成員：市場交易員、風控官、量化分析師。",
            "members": ["市場交易員", "風控官", "量化分析師"]
        }
    ]

    count = 0
    for team_data in teams_config:
        # Check if team exists
        existing_team = db.query(models.Team).filter(models.Team.name == team_data['name']).first()
        if not existing_team:
            # Find member IDs
            member_ids = []
            for member_name in team_data['members']:
                agent = db.query(models.Agent).filter(models.Agent.name == member_name).first()
                if agent:
                    member_ids.append(agent.id)
                else:
                    print(f"Warning: Agent '{member_name}' not found for team '{team_data['name']}'")
            
            if member_ids:
                new_team = models.Team(
                    name=team_data['name'],
                    description=team_data['description'],
                    member_ids=member_ids
                )
                db.add(new_team)
                count += 1
    
    try:
        db.commit()
        if count > 0:
            print(f"Created {count} default teams.")
    except Exception as e:
        print(f"Error creating default teams: {e}")
        db.rollback()

def initialize_companies_and_securities(db: Session):
    """初始化公司與證券（若表為空，從 JSON 種子匯入）"""
    import json
    from datetime import datetime
    from decimal import Decimal
    base = os.path.join("data", "seeds")
    dump_path = os.path.join("data", "companies_seed.json")

    def parse_date(date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    # Companies
    # Priority: dump file (generated by scripts/dump_companies.py) > seed file (manual)
    if not db.query(financial_models.Company).first():
        # Try loading from dump first
        loaded = False
        if os.path.exists(dump_path):
            try:
                print(f"Loading companies from dump: {dump_path}")
                with open(dump_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    
                    # Handle format with metadata
                    if isinstance(content, dict) and "data" in content:
                        companies_data = content["data"]
                        meta = content.get("meta", {})
                        if "date" in meta:
                            Config.update("last_industry_chain_update", meta["date"])
                    else:
                        companies_data = content # Legacy list format
                        
                    for c in companies_data:
                        # Convert float back to Decimal if needed (SQLAlchemy might handle it but better safe)
                        # Actually float is fine for DECIMAL column in SQLite/PG usually via driver
                        db.add(financial_models.Company(**c))
                        
                db.commit()
                print(f"Seeded {len(companies_data)} Companies from dump")
                loaded = True
            except Exception as e:
                print(f"Warning: seed companies from dump failed: {e}")
                db.rollback()
        
        # If dump failed or not exists, try manual seed
        if not loaded:
            path = os.path.join(base, "companies.zh-TW.json")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        seed = json.load(f)
                        for c in seed.get("companies", []):
                            # Parse dates
                            if 'incorporation_date' in c:
                                c['incorporation_date'] = parse_date(c['incorporation_date'])
                            if 'ipo_date' in c:
                                c['ipo_date'] = parse_date(c['ipo_date'])
                            if 'delisting_date' in c:
                                c['delisting_date'] = parse_date(c['delisting_date'])
                            if 'rating_date' in c:
                                c['rating_date'] = parse_date(c['rating_date'])
                            
                            db.add(financial_models.Company(**c))
                    db.commit()
                    print("Seeded Companies from JSON")
                except Exception as e:
                    print(f"Warning: seed companies failed: {e}")
                    db.rollback()
    else:
        print("Companies already exist, skip seeding")

    # Securities
    if not db.query(financial_models.Security).first():
        path = os.path.join(base, "securities.zh-TW.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    seed = json.load(f)
                    for s in seed.get("securities", []):
                        # Parse dates
                        if 'listing_date' in s:
                            s['listing_date'] = parse_date(s['listing_date'])
                        if 'maturity_date' in s:
                            s['maturity_date'] = parse_date(s['maturity_date'])
                        if 'last_price_date' in s:
                            s['last_price_date'] = parse_date(s['last_price_date'])

                        db.add(financial_models.Security(**s))
                db.commit()
                print("Seeded Securities from JSON")
            except Exception as e:
                print(f"Warning: seed securities failed: {e}")
                db.rollback()
    else:
        print("Securities already exist, skip seeding")


def initialize_all(db: Session):
    """執行所有必要的初始化步驟"""
    print("--- Starting System Initialization ---")
    
    try:
        PromptService.initialize_db_from_file(db)
    except Exception as e:
        print(f"Warning: Prompt initialization failed: {e}")

    try:
        ToolSetService.create_global_toolset_if_not_exists(db)
    except Exception as e:
        print(f"Warning: Global ToolSet initialization failed: {e}")

    try:
        initialize_internal_tools(db)
    except Exception as e:
        print(f"Warning: Internal tools initialization failed: {e}")

    try:
        initialize_default_agents(db)
    except Exception as e:
        print(f"Warning: Default Agent initialization failed: {e}")

    # Note: Team agents are now loaded via initialize_default_agents from YAML files
    try:
        initialize_default_teams(db)
    except Exception as e:
        print(f"Warning: Default Team initialization failed: {e}")

    try:
        initialize_toolsets(db)
    except Exception as e:
        print(f"Warning: ToolSet initialization failed: {e}")

    try:
        initialize_financial_terms(db)
    except Exception as e:
        print(f"Warning: Financial Terms initialization failed: {e}")

    try:
        initialize_companies_and_securities(db)
    except Exception as e:
        print(f"Warning: Companies/Securities initialization failed: {e}")

    print("--- System Initialization Complete ---")