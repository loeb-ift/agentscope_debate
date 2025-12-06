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

PROMPTS_AGENTS_DIR = "prompts/agents"

def initialize_financial_terms(db: Session):
    """初始化金融術語對照表"""
    print("Initializing financial terms...")
    
    # Check if any terms exist
    if db.query(models.FinancialTerm).first():
        print("Financial terms already exist, skipping initialization.")
        return

    terms_to_create = []
    for item in FINANCIAL_TERMS_DATA:
        # Check if item is tuple (old format) or dict (new format)
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
        
        term = models.FinancialTerm(
            term_id=term_id,
            term_name=zh_name,
            term_category=category,
            definition=definition
        )
        terms_to_create.append(term)
    
    try:
        db.bulk_save_objects(terms_to_create)
        db.commit()
        print(f"Initialized {len(terms_to_create)} financial terms.")
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
        "internal.get_security_details"
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
    role_toolsets_config = {
        "Quantitative ToolSet": {
            "desc": "量化分析專用：股價、期貨、選擇權",
            "tools": ["tej.stock_price", "tej.futures_data", "tej.options_daily_trading", "tej.financial_cover_cumulative"],
            "target_roles": ["Quantitative Analyst"] 
        },
        "Valuation ToolSet": {
            "desc": "估值建模專用：財報、股利、IFRS",
            "tools": ["tej.financial_summary", "tej.financial_summary_quarterly", "tej.shareholder_meeting", "tej.stock_price", "tej.ifrs_account_descriptions"],
            "target_roles": ["Valuation Expert"]
        },
        "Industry ToolSet": {
            "desc": "產業研究專用：營收、競爭者比較",
            "tools": ["tej.monthly_revenue", "tej.company_info", "tej.financial_summary", "tej.offshore_fund_holdings_industry"],
            "target_roles": ["Industry Researcher"]
        },
        "Risk ToolSet": {
            "desc": "風控合規專用：籌碼、融資券、外資",
            "tools": ["tej.institutional_holdings", "tej.margin_trading", "tej.foreign_holdings", "tej.offshore_fund_suspension"],
            "target_roles": ["Risk & Compliance Officer"]
        },
        "Strategic ToolSet": {
            "desc": "首席/策略專用：公司基本面概覽",
            "tools": ["tej.company_info", "tej.financial_summary"],
            "target_roles": ["Chief Analyst", "Report Editor"]
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
        
        # Assign to matching agents
        for target_role in ts_config["target_roles"]:
            # Find agents whose name contains the target role string
            agents = db.query(models.Agent).filter(models.Agent.name.like(f"%{target_role}%")).all()
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
    """初始化預設 Agent，如果資料庫為空，則從 YAML 文件加載"""
    if db.query(models.Agent).first():
        return

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
                    
                    if db.query(models.Agent).filter(models.Agent.name == item['name']).first():
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
            print(f"Created {len(agents_created)} default agents from files.")
        except Exception as e:
            print(f"Error committing agents: {e}")
            db.rollback()

def initialize_team_agents(db: Session):
    """初始化4個預設團隊的8位辯手"""
    print("Initializing team agents...")
    
    team_agents_config = [
        # Team 1: Growth/Optimist (多頭/成長)
        {
            "name": "Growth_Strategist",
            "role": "debater",
            "specialty": "Growth Investing, Technology Trends, Market Expansion",
            "system_prompt": "你是成長型投資策略師。你專注於尋找具有高增長潛力的公司與產業。你傾向於看好創新、科技突破與市場擴張。你願意承擔較高風險以換取高回報。辯論時，請強調未來的可能性、技術革新與指數級增長。",
            "config": {"temperature": 0.7}
        },
        {
            "name": "Innovation_Believer",
            "role": "debater",
            "specialty": "Disruptive Innovation, Startup Ecosystem, Venture Capital",
            "system_prompt": "你是創新信徒。你堅信顛覆式創新將改變世界。你關注新創生態與獨角獸企業。對於傳統觀點，你常持挑戰態度。辯論時，請多引用科技巨頭的發展史與新興技術的潛力。",
            "config": {"temperature": 0.8}
        },
        
        # Team 2: Value/Conservative (空頭/價值)
        {
            "name": "Value_Investor",
            "role": "debater",
            "specialty": "Fundamental Analysis, Financial Statements, Margin of Safety",
            "system_prompt": "你是價值投資者。你信奉班傑明·葛拉漢與巴菲特的哲學。你注重安全邊際，尋找被低估的資產。你對高估值的熱門股持懷疑態度。辯論時，請強調基本面數據（PE, PB, Cash Flow）與下行風險保護。",
            "config": {"temperature": 0.5}
        },
        {
            "name": "Risk_Manager",
            "role": "debater",
            "specialty": "Risk Assessment, Bear Market History, Capital Preservation",
            "system_prompt": "你是風控經理。你的首要任務是資本保全。你對市場泡沫與極端情緒非常敏感。你總是能看到潛在的危機與黑天鵝。辯論時，請專注於揭示潛在風險、債務問題與宏觀不確定性。",
            "config": {"temperature": 0.4}
        },
        
        # Team 3: Macro/Policy (宏觀/政策)
        {
            "name": "Macro_Economist",
            "role": "debater",
            "specialty": "Monetary Policy, Fiscal Policy, Global Trade",
            "system_prompt": "你是宏觀經濟學家。你關注GDP、通膨、利率與匯率。你從全球經濟周期的角度分析問題。辯論時，請引用央行政策、經濟數據與國際地緣政治的影響。",
            "config": {"temperature": 0.6}
        },
        {
            "name": "Policy_Analyst",
            "role": "debater",
            "specialty": "Regulations, Government Strategy, Industrial Policy",
            "system_prompt": "你是政策分析師。你專注於政府法規、產業政策與合規性。你分析政府行為對市場的長遠影響。辯論時，請強調監管環境、稅收政策與國家戰略方向。",
            "config": {"temperature": 0.5}
        },
        
        # Team 4: Technical/Short-term (技術/短線)
        {
            "name": "Technical_Analyst",
            "role": "debater",
            "specialty": "Chart Patterns, Technical Indicators, Market Psychology",
            "system_prompt": "你是技術分析師。你相信價格反映一切。你關注K線圖、趨勢線、支撐壓力位與成交量。辯論時，請基於圖表型態、資金流向與市場情緒進行論證。",
            "config": {"temperature": 0.7}
        },
        {
            "name": "Market_Trader",
            "role": "debater",
            "specialty": "Short-term Trading, Volatility, Momentum",
            "system_prompt": "你是市場交易員。你關注短期的波動與動能。你對長期基本面不感興趣，只在乎當下的趨勢與獲利機會。辯論時，請強調即時的市場反應、流動性與交易機會。",
            "config": {"temperature": 0.8}
        }
    ]

    count = 0
    for agent_data in team_agents_config:
        existing = db.query(models.Agent).filter(models.Agent.name == agent_data['name']).first()
        if not existing:
            new_agent = models.Agent(
                name=agent_data['name'],
                role=agent_data['role'],
                specialty=agent_data['specialty'],
                system_prompt=agent_data['system_prompt'],
                config_json=agent_data.get('config', {})
            )
            db.add(new_agent)
            count += 1
    
    try:
        db.commit()
        if count > 0:
            print(f"Created {count} team agents.")
    except Exception as e:
        print(f"Error creating team agents: {e}")
        db.rollback()

def initialize_default_teams(db: Session):
    """初始化4個預設辯論團隊 (Teams)"""
    print("Initializing default teams...")

    teams_config = [
        {
            "name": "Growth Team",
            "description": "專注於高成長與創新科技 (Members: Growth_Strategist, Innovation_Believer)",
            "members": ["Growth_Strategist", "Innovation_Believer"]
        },
        {
            "name": "Value Team",
            "description": "專注於基本面與風險控制 (Members: Value_Investor, Risk_Manager)",
            "members": ["Value_Investor", "Risk_Manager"]
        },
        {
            "name": "Macro Team",
            "description": "專注於宏觀經濟與政策分析 (Members: Macro_Economist, Policy_Analyst)",
            "members": ["Macro_Economist", "Policy_Analyst"]
        },
        {
            "name": "Technical Team",
            "description": "專注於技術分析與市場動能 (Members: Technical_Analyst, Market_Trader)",
            "members": ["Technical_Analyst", "Market_Trader"]
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

    try:
        initialize_team_agents(db)
    except Exception as e:
        print(f"Warning: Team Agent initialization failed: {e}")

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

    print("--- System Initialization Complete ---")