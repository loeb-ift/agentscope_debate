
import sys
sys.path.insert(0, '/app')

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import redis
import json
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from api import schemas, models
from api.database import SessionLocal, engine, init_db
from worker.celery_app import app as celery_app
from api.tool_registry import tool_registry
from adapters.searxng_adapter import SearXNGAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.yfinance_adapter import YFinanceAdapter
from adapters.tej_adapter import (
    TEJCompanyInfo, TEJStockPrice, TEJMonthlyRevenue, TEJInstitutionalHoldings,
    TEJMarginTrading, TEJForeignHoldings, TEJFinancialSummary, TEJFundNAV,
    TEJShareholderMeeting, TEJFundBasicInfo, TEJOffshoreFundInfo, TEJOffshoreFundDividend,
    TEJOffshoreFundHoldingsRegion, TEJOffshoreFundHoldingsIndustry, TEJOffshoreFundNAVRank,
    TEJOffshoreFundNAVDaily, TEJOffshoreFundSuspension, TEJOffshoreFundPerformance,
    TEJIFRSAccountDescriptions, TEJFinancialCoverCumulative, TEJFinancialSummaryQuarterly,
    TEJFinancialCoverQuarterly, TEJFuturesData, TEJOptionsBasicInfo, TEJOptionsDailyTrading
)

# 初始化資料庫
init_db()

# 註冊工具
tool_registry.register(SearXNGAdapter())
tool_registry.register(DuckDuckGoAdapter())
tool_registry.register(YFinanceAdapter())
tool_registry.register(TEJCompanyInfo())
tool_registry.register(TEJStockPrice())
tool_registry.register(TEJMonthlyRevenue())
tool_registry.register(TEJInstitutionalHoldings())
tool_registry.register(TEJMarginTrading())
tool_registry.register(TEJForeignHoldings())
tool_registry.register(TEJFinancialSummary())
tool_registry.register(TEJFundNAV())
tool_registry.register(TEJShareholderMeeting())
tool_registry.register(TEJFundBasicInfo())
tool_registry.register(TEJOffshoreFundInfo())
tool_registry.register(TEJOffshoreFundDividend())
tool_registry.register(TEJOffshoreFundHoldingsRegion())
tool_registry.register(TEJOffshoreFundHoldingsIndustry())
tool_registry.register(TEJOffshoreFundNAVRank())
tool_registry.register(TEJOffshoreFundNAVDaily())
tool_registry.register(TEJOffshoreFundSuspension())
tool_registry.register(TEJOffshoreFundPerformance())
tool_registry.register(TEJIFRSAccountDescriptions())
tool_registry.register(TEJFinancialCoverCumulative())
tool_registry.register(TEJFinancialSummaryQuarterly())
tool_registry.register(TEJFinancialCoverQuarterly())
tool_registry.register(TEJFuturesData())
tool_registry.register(TEJOptionsBasicInfo())
tool_registry.register(TEJOptionsDailyTrading())

app = FastAPI()

# Redis 連線
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)



# Dependency
def get_db():
    """
    獲取資料庫 session 的相依性函數。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Agent Management API ---

@app.get("/api/v1/agents", response_model=List[schemas.Agent])
def list_agents(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    列出所有 Agent。
    可選參數：
    - skip: 跳過的數量（分頁）
    - limit: 返回的最大數量
    - role: 篩選角色（debater, chairman, analyst）
    """
    query = db.query(models.Agent)
    
    if role:
        query = query.filter(models.Agent.role == role)
    
    agents = query.offset(skip).limit(limit).all()
    return agents

@app.post("/api/v1/agents", response_model=schemas.Agent, status_code=201)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    """
    創建新的 Agent。
    """
    # 驗證角色
    valid_roles = ['debater', 'chairman', 'analyst']
    if agent.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    # 創建 Agent
    db_agent = models.Agent(
        name=agent.name,
        role=agent.role,
        specialty=agent.specialty,
        system_prompt=agent.system_prompt,
        config_json=agent.config_json
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    return db_agent

@app.get("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    獲取特定 Agent 的詳細資訊。
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent

@app.put("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def update_agent(
    agent_id: str,
    agent_update: schemas.AgentUpdate,
    db: Session = Depends(get_db)
):
    """
    更新 Agent 的資訊。
    只更新提供的欄位（部分更新）。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 更新提供的欄位
    update_data = agent_update.dict(exclude_unset=True)
    
    # 驗證角色（如果提供）
    if 'role' in update_data:
        valid_roles = ['debater', 'chairman', 'analyst']
        if update_data['role'] not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
    
    for field, value in update_data.items():
        setattr(db_agent, field, value)
    
    db.commit()
    db.refresh(db_agent)
    
    return db_agent

@app.delete("/api/v1/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    刪除 Agent。
    注意：如果 Agent 正在被使用中的辯論引用，應該先檢查。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # TODO: 檢查是否有正在進行的辯論使用此 Agent
    
    db.delete(db_agent)
    db.commit()
    
    return None

@app.get("/api/v1/agents/roles/available")
def get_available_roles():
    """
    獲取可用的 Agent 角色列表。
    """
    return {
        "roles": [
            {
                "value": "debater",
                "label": "辯士",
                "description": "參與辯論的 Agent"
            },
            {
                "value": "chairman",
                "label": "主席",
                "description": "主持辯論、進行分析和總結的 Agent"
            },
            {
                "value": "analyst",
                "label": "分析師",
                "description": "專門進行數據分析的 Agent"
            }
        ]
    }

# --- ToolSet Management API ---

from api import toolset_schemas
from api.toolset_service import ToolSetService

@app.post("/api/v1/toolsets", response_model=toolset_schemas.ToolSet, status_code=201)
def create_toolset(toolset: toolset_schemas.ToolSetCreate, db: Session = Depends(get_db)):
    """創建新的工具集"""
    db_toolset = models.ToolSet(
        name=toolset.name,
        description=toolset.description,
        tool_names=toolset.tool_names,
        is_global=toolset.is_global
    )
    db.add(db_toolset)
    db.commit()
    db.refresh(db_toolset)
    return db_toolset

@app.get("/api/v1/toolsets", response_model=List[toolset_schemas.ToolSet])
def list_toolsets(
    skip: int = 0,
    limit: int = 100,
    is_global: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """列出所有工具集"""
    query = db.query(models.ToolSet)
    if is_global is not None:
        query = query.filter(models.ToolSet.is_global == is_global)
    return query.offset(skip).limit(limit).all()

@app.get("/api/v1/toolsets/{toolset_id}")
def get_toolset(toolset_id: str, db: Session = Depends(get_db)):
    """獲取工具集詳情（包含工具列表）"""
    toolset_details = ToolSetService.get_toolset_details(db, toolset_id)
    if not toolset_details:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    return toolset_details

@app.put("/api/v1/toolsets/{toolset_id}", response_model=toolset_schemas.ToolSet)
def update_toolset(
    toolset_id: str,
    toolset_update: toolset_schemas.ToolSetUpdate,
    db: Session = Depends(get_db)
):
    """更新工具集"""
    db_toolset = db.query(models.ToolSet).filter(models.ToolSet.id == toolset_id).first()
    if not db_toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    update_data = toolset_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_toolset, field, value)
    
    db.commit()
    db.refresh(db_toolset)
    return db_toolset

@app.delete("/api/v1/toolsets/{toolset_id}", status_code=204)
def delete_toolset(toolset_id: str, db: Session = Depends(get_db)):
    """刪除工具集"""
    db_toolset = db.query(models.ToolSet).filter(models.ToolSet.id == toolset_id).first()
    if not db_toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    if db_toolset.is_global:
        raise HTTPException(status_code=400, detail="Cannot delete global toolset")
    
    db.query(models.AgentToolSet).filter(models.AgentToolSet.toolset_id == toolset_id).delete()
    db.delete(db_toolset)
    db.commit()
    return None

# Agent-ToolSet Association

@app.post("/api/v1/agents/{agent_id}/toolsets", response_model=toolset_schemas.AgentToolSetResponse, status_code=201)
def assign_toolset_to_agent(
    agent_id: str,
    assignment: toolset_schemas.AgentToolSetAssign,
    db: Session = Depends(get_db)
):
    """分配工具集給 Agent"""
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    toolset = db.query(models.ToolSet).filter(models.ToolSet.id == assignment.toolset_id).first()
    if not toolset:
        raise HTTPException(status_code=404, detail="ToolSet not found")
    
    existing = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id,
        models.AgentToolSet.toolset_id == assignment.toolset_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="ToolSet already assigned")
    
    db_assignment = models.AgentToolSet(agent_id=agent_id, toolset_id=assignment.toolset_id)
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    return db_assignment

@app.get("/api/v1/agents/{agent_id}/toolsets")
def get_agent_toolsets(agent_id: str, db: Session = Depends(get_db)):
    """獲取 Agent 的所有工具集"""
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    assigned_toolsets = []
    agent_toolsets = db.query(models.AgentToolSet).filter(models.AgentToolSet.agent_id == agent_id).all()
    
    for ats in agent_toolsets:
        toolset = db.query(models.ToolSet).filter(models.ToolSet.id == ats.toolset_id).first()
        if toolset:
            assigned_toolsets.append({
                "id": toolset.id,
                "name": toolset.name,
                "description": toolset.description,
                "tool_count": len(toolset.tool_names),
                "source": "assigned"
            })
    
    global_toolsets = db.query(models.ToolSet).filter(models.ToolSet.is_global == True).all()
    for toolset in global_toolsets:
        assigned_toolsets.append({
            "id": toolset.id,
            "name": toolset.name,
            "description": toolset.description,
            "tool_count": len(toolset.tool_names),
            "source": "global"
        })
    
    return {"agent_id": agent_id, "agent_name": agent.name, "toolsets": assigned_toolsets}

@app.get("/api/v1/agents/{agent_id}/available-tools")
def get_agent_available_tools(agent_id: str, db: Session = Depends(get_db)):
    """獲取 Agent 可用的所有工具"""
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ToolSetService.get_agent_available_tools(db, agent_id)

@app.delete("/api/v1/agents/{agent_id}/toolsets/{toolset_id}", status_code=204)
def remove_toolset_from_agent(agent_id: str, toolset_id: str, db: Session = Depends(get_db)):
    """移除 Agent 的工具集分配"""
    assignment = db.query(models.AgentToolSet).filter(
        models.AgentToolSet.agent_id == agent_id,
        models.AgentToolSet.toolset_id == toolset_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(assignment)
    db.commit()
    return None

@app.post("/api/v1/toolsets/initialize-global")
def initialize_global_toolset(db: Session = Depends(get_db)):
    """初始化全局工具集"""
    return ToolSetService.create_global_toolset_if_not_exists(db)

# --- Debates API ---

@app.post("/api/v1/debates", status_code=201)
def create_debate(debate: schemas.DebateCreate, background_tasks: BackgroundTasks):
    """
    創建一個新的辯論。
    接收辯論主題和配置，並觸發背景任務開始辯論。
    """
    # 提供預設配置
    config = debate.config or {}
    pro_team = config.get('pro_team', [])
    con_team = config.get('con_team', [])
    rounds = config.get('rounds', 3)
    
    task = celery_app.send_task(
        'worker.tasks.run_debate_cycle', 
        args=[
            debate.topic,
            pro_team, 
            con_team, 
            rounds
        ]
    )
    # 將任務 ID 存儲到 Redis，以便後續查詢
    redis_client.set(f"debate:{task.id}:topic", debate.topic)
    return {"task_id": task.id, "status": "Debate started"}

@app.get("/api/v1/debates", response_model=List[schemas.DebateArchive])
def list_debates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    列出所有已存檔的辯論。
    """
    debates = db.query(models.DebateArchive).offset(skip).limit(limit).all()
    return debates


@app.get("/api/v1/debates/{task_id}")
def get_debate_status(task_id: str):
    """
    根據任務 ID 獲取辯論的當前狀態。
    """
    status = celery_app.AsyncResult(task_id).status
    topic = redis_client.get(f"debate:{task_id}:topic")
    if not topic:
        raise HTTPException(status_code=404, detail="Debate not found")
    return {"task_id": task_id, "topic": topic, "status": status}

@app.get("/api/v1/debates/{task_id}/stream")
async def stream_debate(task_id: str):
    """
    透過 Server-Sent Events (SSE) 實時串流辯論的思考流。
    """
    def event_stream():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"debate:{task_id}:log_stream")
        for message in pubsub.listen():
            if message['type'] == 'message':
                yield f"data: {message['data']}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Agents API ---

@app.get("/tools")
def list_tools():
    """
    列出所有可用的工具。
    """
    return {"tools": [tool["instance"].name for tool in tool_registry.get_tools()]}


@app.post("/api/v1/agents", response_model=schemas.Agent)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    """
    創建一個新的智能體。
    """
    db_agent = models.Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/api/v1/agents", response_model=List[schemas.Agent])
def list_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    列出所有智能體。
    """
    agents = db.query(models.Agent).offset(skip).limit(limit).all()
    return agents

@app.get("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    """
    獲取指定智能體的詳細資訊。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent

@app.put("/api/v1/agents/{agent_id}", response_model=schemas.Agent)
def update_agent(agent_id: int, agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    """
    更新指定智能體的資訊。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    for key, value in agent.dict().items():
        setattr(db_agent, key, value)
        
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/api/v1/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """
    刪除指定智能體。
    """
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    db.delete(db_agent)
    db.commit()
    return 

# --- Tools API ---

@app.get("/api/v1/tools")
def list_tools():
    """
    列出所有已註冊的工具。
    """
    tools = tool_registry.list()
    # 修正：由於 list() 不再返回 instance，我們需要一種方法來獲取工具名稱
    # 這裡我們假設 tool_id 的格式為 "name:version"
    return {
        name.split(':')[0]: {
            "name": name.split(':')[0],
            "description": data["description"]["description"],
            "version": data["version"],
        }
        for name, data in tools.items()
    }

from jsonschema import validate, ValidationError
@app.post("/api/v1/tools/test")
async def test_tool(tool_test: schemas.ToolTest):
    """
    測試單一工具的執行，包括參數驗證和快取。
    """
    result = tool_registry.invoke_tool(tool_test.name, tool_test.kwargs)
    if "error" in result:
        # 根據錯誤類型返回不同的狀態碼
        if "Parameter validation failed" in result["error"]:
            raise HTTPException(status_code=400, detail=result["error"])
        else:
            raise HTTPException(status_code=404, detail=result["error"])
    return {"tool": tool_test.name, "result": result}


