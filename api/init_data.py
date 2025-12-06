from sqlalchemy.orm import Session
from api import models
from api.prompt_service import PromptService
from api.toolset_service import ToolSetService
import yaml
import os
import glob

PROMPTS_AGENTS_DIR = "prompts/agents"

def initialize_toolsets(db: Session):
    """初始化預設工具集並分配給 Agent"""
    print("Initializing toolsets...")
    
    # 1. Global Standard ToolSet (Search + Yahoo Finance)
    global_tools = ["searxng.search", "duckduckgo.search", "yfinance.stock_info"]
    
    global_ts = db.query(models.ToolSet).filter(models.ToolSet.is_global == True).first()
    if not global_ts:
        global_ts = models.ToolSet(
            name="Global Standard Tools",
            description="基礎搜尋與國際財經資訊工具",
            tool_names=global_tools,
            is_global=True
        )
        db.add(global_ts)
    else:
        # Update existing global toolset to ensure it has yfinance
        current_tools = set(global_ts.tool_names)
        if "yfinance.stock_info" not in current_tools:
            global_ts.tool_names = list(current_tools | {"yfinance.stock_info"})
    
    db.commit()
    db.refresh(global_ts)

    # 2. Role-Specific ToolSets
    role_toolsets_config = {
        "Quantitative ToolSet": {
            "desc": "量化分析專用：股價、期貨、選擇權",
            "tools": ["tej.stock_price", "tej.futures_data", "tej.options_daily_trading", "tej.financial_cover_cumulative"],
            "target_roles": ["Quantitative Analyst"] # Partial match on English name
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


def initialize_default_agents(db: Session):
    """初始化預設 Agent，如果資料庫為空，則從 YAML 文件加載"""
    if db.query(models.Agent).first():
        # Even if agents exist, we might want to ensure toolsets are assigned
        # But let's stick to the "init" logic
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
                # Some files might contain multiple docs or just one
                # yaml.safe_load loads a single document
                data = yaml.safe_load(f)
                if not data: continue
                
                # Handle if file contains a list or single dict
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if not item.get('name'): continue
                    
                    # Check exist (by name)
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

def initialize_all(db: Session):
    """執行所有必要的初始化步驟"""
    print("--- Starting System Initialization ---")
    
    # 1. 初始化 Prompt
    try:
        PromptService.initialize_db_from_file(db)
    except Exception as e:
        print(f"Warning: Prompt initialization failed: {e}")

    # 2. 初始化 Default Agents
    try:
        initialize_default_agents(db)
    except Exception as e:
        print(f"Warning: Default Agent initialization failed: {e}")

    # 3. 初始化 ToolSets & Assignment (Depend on Agents existing)
    try:
        initialize_toolsets(db)
    except Exception as e:
        print(f"Warning: ToolSet initialization failed: {e}")

    print("--- System Initialization Complete ---")