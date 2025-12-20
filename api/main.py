
import sys
sys.path.insert(0, '/app')

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from api import schemas, models, financial_models
from api.database import SessionLocal, engine, init_db
from api.init_data import initialize_all
from api.toolset_service import ToolSetService
from worker.celery_app import app as celery_app, load_dynamic_tools
from api.config import Config
from api.tool_registry import tool_registry
from api.redis_client import get_redis_client
from adapters.searxng_adapter import SearXNGAdapter
from adapters.duckduckgo_adapter import DuckDuckGoAdapter
from adapters.yfinance_adapter import YFinanceAdapter
# Lazy import helper for conditional tools
def lazy_import_factory(module_name, class_name):
    def factory():
        import importlib
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        return cls()
    return factory

from adapters.tej_adapter import (
    TEJCompanyInfo, TEJStockPrice, TEJMonthlyRevenue, TEJInstitutionalHoldings,
    TEJMarginTrading, TEJForeignHoldings, TEJFinancialSummary, TEJFundNAV,
    TEJShareholderMeeting, TEJFundBasicInfo, TEJOffshoreFundInfo, TEJOffshoreFundDividend,
    TEJOffshoreFundHoldingsRegion, TEJOffshoreFundHoldingsIndustry, TEJOffshoreFundNAVRank,
    TEJOffshoreFundNAVDaily, TEJOffshoreFundSuspension, TEJOffshoreFundPerformance,
    TEJIFRSAccountDescriptions, TEJFinancialCoverCumulative, TEJFinancialSummaryQuarterly,
    TEJFinancialCoverQuarterly, TEJFuturesData, TEJOptionsBasicInfo, TEJOptionsDailyTrading
)

# FastAPI app 先創建
app = FastAPI()

import time
from fastapi import Request

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    print(f"Request: {request.method} {request.url.path} completed in {process_time:.4f}s")
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis 連線
redis_client = get_redis_client()

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

@app.on_event("startup")
async def startup_event():
    """在 API 服務啟動時執行初始化"""
    print("🚀 Starting API initialization...")
    
    # 初始化資料庫
    init_db()
    
    # 執行系統初始化 (Prompt, ToolSet, Default Agents)
    db = SessionLocal()
    try:
        initialize_all(db)
    finally:
        db.close()
    
    # 註冊工具
    print("📦 Registering tools...")
    tool_registry.register(SearXNGAdapter())
    tool_registry.register(DuckDuckGoAdapter())
    tool_registry.register(YFinanceAdapter())
    
    # Register ODS Internal Adapter
    from adapters.ods_internal_adapter import ODSInternalAdapter
    tool_registry.register(ODSInternalAdapter())
    
    # Register EDA Tool Adapter (Chairman Only)
    from adapters.eda_tool_adapter import EDAToolAdapter
    tool_registry.register(EDAToolAdapter())
    
    # ChinaTimes Suite (Conditional)
    if Config.ENABLE_CHINATIMES_TOOLS:
        print("📰 Registering ChinaTimes tools...")
        tool_registry.register_lazy("news.search_chinatimes", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesSearchAdapter"), group="browser_use", description="[PRIORITY] Search ChinaTimes News for Taiwan related topics")
        tool_registry.register_lazy("chinatimes.stock_rt", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesStockRTAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Realtime Stock Data")
        tool_registry.register_lazy("chinatimes.stock_news", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesStockNewsAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Stock News")
        tool_registry.register_lazy("chinatimes.stock_kline", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesStockKlineAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Stock K-Line History (Day K)")
        tool_registry.register_lazy("chinatimes.market_index", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesMarketIndexAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Market Indexes (TWSE/OTC)")
        tool_registry.register_lazy("chinatimes.market_rankings", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesMarketRankingsAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Market Rankings (Top 10)")
        tool_registry.register_lazy("chinatimes.sector_info", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesSectorAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Sector Info")
        tool_registry.register_lazy("chinatimes.stock_fundamental", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesStockFundamentalAdapter"), group="financial_data", description="[PRIORITY] ChinaTimes Stock Fundamental Check")
        # Financial Statements
        tool_registry.register_lazy("chinatimes.balance_sheet", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesBalanceSheetAdapter"), group="financial_data", description="ChinaTimes Balance Sheet")
        tool_registry.register_lazy("chinatimes.income_statement", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesIncomeStatementAdapter"), group="financial_data", description="ChinaTimes Income Statement")
        tool_registry.register_lazy("chinatimes.cash_flow", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesCashFlowAdapter"), group="financial_data", description="ChinaTimes Cash Flow Statement")
        tool_registry.register_lazy("chinatimes.financial_ratios", lazy_import_factory("adapters.chinatimes_suite", "ChinaTimesFinancialRatiosAdapter"), group="financial_data", description="ChinaTimes Financial Ratios")

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
    
    # 載入動態工具 (DB-based)
    load_dynamic_tools()
    
    print("✅ API initialization complete!")

# Configure toolset cache backend (Memory by default; switchable to Redis via env)
from api.cache_backends import MemoryCache, RedisCache
import os
if os.getenv("EFFECTIVE_TOOLS_CACHE", "memory").lower() == "redis":
    ToolSetService.configure_cache_backend(RedisCache())
else:
    ToolSetService.configure_cache_backend(MemoryCache())

# --- Include Routers ---
from api.agent_routes import router as agent_router
from api.debate_routes import router as debate_router
from api.prompt_routes import router as prompt_router
from api.tool_routes import router as tool_router
from api.internal_api import router as internal_router
from api.toolset_routes import router as toolset_router
from api.routers.cache_management import router as cache_router
from api.routers.eda_routes import router as eda_router

app.include_router(agent_router)
app.include_router(debate_router)
app.include_router(prompt_router)
app.include_router(tool_router)
app.include_router(internal_router)
app.include_router(toolset_router)
app.include_router(cache_router, prefix="/api/v1")
app.include_router(eda_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """健康檢查端點，用於確認服務已就緒"""
    return {"status": "healthy", "service": "debate-api"}

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
        print(f"[DEBUG API] Client connected to stream for task {task_id}", flush=True)
        # 1. Send historical logs first
        history_key = f"debate:{task_id}:log_history"
        try:
            history = redis_client.lrange(history_key, 0, -1)
            print(f"[DEBUG API] Found {len(history)} history items for {task_id}", flush=True)
            for log_json in history:
                yield f"data: {log_json}\n\n"
        except Exception as e:
            print(f"Error fetching log history: {e}", flush=True)

        # Send initial zero usage (Send this FIRST to unblock frontend)
        import time
        import json
        last_cost_check = 0
        yield f"data: {json.dumps({'type': 'usage_update', 'tokens': 0, 'cost': 0.0, 'search_count': 0})}\n\n"

        # 2. Subscribe to new logs
        try:
            print(f"[DEBUG API] Subscribing to debate:{task_id}:log_stream", flush=True)
            pubsub = redis_client.pubsub()
            pubsub.subscribe(f"debate:{task_id}:log_stream")
        except Exception as e:
            print(f"Error subscribing to Redis: {e}", flush=True)
            yield f"data: {json.dumps({'role': 'System', 'content': f'❌ Redis 訂閱失敗: {str(e)}'})}\n\n"
            return

        # Use get_message() loop to allow periodic cost updates
        while True:
            # Check for Redis messages
            message = pubsub.get_message(timeout=0.1)
            
            if message and message['type'] == 'message':
                msg_data = message['data']
                if isinstance(msg_data, bytes):
                    msg_data = msg_data.decode('utf-8')
                
                yield f"data: {msg_data}\n\n"
                
                if msg_data == "[DONE]":
                    break
            
            # Periodic Cost Update (every 2s)
            now = time.time()
            if now - last_cost_check > 2:
                try:
                    usage = redis_client.hgetall(f"debate:{task_id}:usage")
                    if usage:
                        # Decode bytes if needed (redis-py returns bytes for hgetall)
                        tokens = int(usage.get(b"total_tokens", 0) or usage.get("total_tokens", 0))
                        cost = float(usage.get(b"total_cost", 0.0) or usage.get("total_cost", 0.0))
                        search_count = int(usage.get(b"search_count", 0) or usage.get("search_count", 0))
                        
                        event_data = {
                            "type": "usage_update",
                            "tokens": tokens,
                            "cost": cost,
                            "search_count": search_count
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                except Exception:
                    pass
                last_cost_check = now
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Agents API ---

# (Removed duplicate Agent APIs that were inadvertently added at the end)

# --- Tools API ---

@app.get("/api/v1/registry/tools")
def list_registry_tools():
    """
    列出所有已註冊的工具（包括代碼與動態工具）。
    返回統一結構，並安全處理描述欄位：
    {
      "tool.name": {"name": "tool.name", "version": "v1", "description": "...", "group": "...", "schema": {...}}
    }
    """
    tools = tool_registry.list_tools()  # returns internal dict {tool_id: data}
    normalized = {}
    for tool_id, data in tools.items():
        # tool_id format: name:version
        try:
            name, version = tool_id.split(":", 1)
        except ValueError:
            name, version = tool_id, data.get("version", "v1")
        desc = data.get("description")
        # description may be a string or a dict from adapter.describe()
        if isinstance(desc, dict):
            desc = (
                desc.get("description")
                or desc.get("desc")
                or desc.get("summary")
                or str(desc)
            )
        elif desc is None:
            desc = ""
        normalized[name] = {
            "name": name,
            "version": version,
            "description": desc,
            "group": data.get("group"),
            "schema": data.get("schema"),
        }
    return normalized

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


