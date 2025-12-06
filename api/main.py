
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
from api.init_data import initialize_all
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

# 執行系統初始化 (Prompt, ToolSet, Default Agents)
db = SessionLocal()
try:
    initialize_all(db)
finally:
    db.close()

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

# --- Include Routers ---
from api.agent_routes import router as agent_router
from api.debate_routes import router as debate_router
from api.prompt_routes import router as prompt_router
from api.tool_routes import router as tool_router

app.include_router(agent_router)
app.include_router(debate_router)
app.include_router(prompt_router)
app.include_router(tool_router)

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

# 注意：主要辯論配置與啟動邏輯已移至 api/debate_routes.py
# 這裡保留一些共享的查詢 endpoint (如 list_debates)

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

# (Removed duplicate Agent APIs that were inadvertently added at the end)

# --- Tools API ---

@app.get("/api/v1/registry/tools")
def list_registry_tools():
    """
    列出所有已註冊的工具（包括代碼與動態工具）。
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


