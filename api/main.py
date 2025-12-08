
import sys
sys.path.insert(0, '/app')

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import redis
import json
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from api import schemas, models, financial_models
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
from api.internal_api import router as internal_router
from api.toolset_routes import router as toolset_router

app.include_router(agent_router)
app.include_router(debate_router)
app.include_router(prompt_router)
app.include_router(tool_router)
app.include_router(internal_router)
app.include_router(toolset_router)

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


