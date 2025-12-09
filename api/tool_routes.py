from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from api import schemas, models
from api.database import SessionLocal
from api.tool_registry import tool_registry
from adapters.http_tool_adapter import HTTPToolAdapter
import time
from adapters.python_tool_adapter import PythonToolAdapter
from worker.llm_utils import call_llm
from api.prompt_service import PromptService

router = APIRouter()

TEJ_STOCK_PRICE_TEMPLATE = {
    "name": "custom.stock_price",
    "type": "http",
    "description": "示範：查詢台股個股歷史價格（以 TEJ OpenAPI 風格為例，可自行改成自家 REST 服務）",
    "version": "v1",
    "api_config": {
        "url": "https://example.com/tej/stock_price",  # 請改為你的 API URL
        "method": "GET",
        "headers": {
            "User-Agent": "AgentScope/1.0"
        }
    },
    "json_schema": {
        "type": "object",
        "properties": {
            "coid": {"type": "string", "description": "公司代碼，如 2330"},
            "mdate.gte": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
            "mdate.lte": {"type": "string", "description": "結束日期 YYYY-MM-DD"},
            "opts.limit": {"type": "integer", "default": 10},
            "opts.offset": {"type": "integer", "default": 0}
        },
        "required": ["coid"]
    },
    "example_params": {
        "coid": "2330",
        "mdate.gte": "2024-01-01",
        "mdate.lte": "2024-01-05",
        "opts.limit": 5,
        "opts.offset": 0,
        "api_key": "${TEJ_API_KEY}"  # 若你的 API 需要金鑰，請在後端轉換為 Header 或 Query
    }
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/v1/tools", response_model=List[schemas.Tool])
def list_tools(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """列出所有資料庫中的自定義工具（含一個 TEJ 範例模板）"""
    tools = db.query(models.Tool).offset(skip).limit(limit).all()
    return tools

@router.get("/api/v1/tools/templates/tej-stock-price")
def get_tej_stock_price_template():
    """提供一個可直接在前端載入的 TEJ 風格工具模板（示例）。
    使用者可以：
      1) 直接 Try-it-out 測試（需改成自己的 URL 或使用已接通的 TEJ 代理）
      2) 複製為新工具後按需修改欄位
    前端可提示：請將 ${TEJ_API_KEY} 設定於 .env 並在後端適配為 header/query。
    """
    return TEJ_STOCK_PRICE_TEMPLATE

@router.post("/api/v1/tools", response_model=schemas.Tool, status_code=201)
def create_tool(tool: schemas.ToolCreate, db: Session = Depends(get_db)):
    """創建新的自定義工具並註冊"""
    db_tool = models.Tool(**tool.dict())
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    
    # 動態註冊到 Registry
    if db_tool.enabled:
        adapter = None
        if db_tool.type == "http":
            adapter = HTTPToolAdapter(
                name=db_tool.name,
                description=db_tool.description or "User defined HTTP tool",
                api_config=db_tool.api_config,
                schema=db_tool.json_schema
            )
        elif db_tool.type == "python":
            adapter = PythonToolAdapter(
                name=db_tool.name,
                description=db_tool.description or "User defined Python tool",
                python_code=db_tool.python_code,
                schema=db_tool.json_schema
            )
            
        if adapter:
            tool_registry.register(adapter, group=db_tool.group)
        
    return db_tool

@router.get("/api/v1/tools/{tool_id}", response_model=schemas.Tool)
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    """獲取單個工具的詳細資訊"""
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return db_tool

@router.put("/api/v1/tools/{tool_id}", response_model=schemas.Tool)
def update_tool(tool_id: int, tool_update: schemas.ToolUpdate, db: Session = Depends(get_db)):
    """更新自定義工具"""
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    # Update fields
    update_data = tool_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tool, key, value)
    
    db.commit()
    db.refresh(db_tool)
    
    # Re-register if enabled (basic implementation: register overwrites)
    if db_tool.enabled:
        if db_tool.type in ("http", "api") and db_tool.api_config:
            try:
                adapter = HTTPToolAdapter(
                    name=db_tool.name,
                    description=db_tool.description or "User defined HTTP tool",
                    api_config=db_tool.api_config,
                    schema=db_tool.json_schema,
                )
                tool_registry.register(adapter, group=db_tool.group)
            except Exception:
                # 如果重新註冊失敗，先不阻塞更新流程
                pass
    return db_tool

@router.delete("/api/v1/tools/{tool_id}", status_code=204)
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    """刪除自定義工具"""
    db_tool = db.query(models.Tool).filter(models.Tool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    db.delete(db_tool)
    db.commit()
    return None

@router.post("/api/v1/tools/generate-description")
def generate_tool_description(req: schemas.ToolDescriptionGenerate):
    """使用 LLM 自動生成工具描述"""
    
    db = SessionLocal()
    try:
        default_system = """You are an expert tool documenter for AI agents.
Your task is to analyze the provided tool code or API schema and write a concise, clear description.
The description should explain WHAT the tool does and WHEN an agent should use it.
Also briefly mention the key parameters if they are not obvious.
Keep it under 3 sentences if possible."""
        sys_template = PromptService.get_prompt(db, "tool.generate_description_system", default=default_system)
        system_prompt = sys_template

        default_user = """
Tool Type: {tool_type}
Content:
{content}

Please generate a description for this tool:"""
        user_template = PromptService.get_prompt(db, "tool.generate_description_user", default=default_user)
        user_prompt = user_template.format(tool_type=req.tool_type, content=req.content)
    finally:
        db.close()

    try:
        description = call_llm(user_prompt, system_prompt=system_prompt)
        return {"description": description.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

@router.post("/api/v1/tools/try-run", response_model=schemas.ToolTryRunResponse)
def try_run_tool(req: schemas.ToolTryRunRequest = Body(...)):
    """臨時執行工具（不入庫），用於前端 Try-it-out。
    - 僅支援 http/api 工具型別
    - 直接構建 HTTPToolAdapter 並 invoke
    - 回傳 request/response 摘要與預覽資料
    """
    if req.type not in ("http", "api"):
        raise HTTPException(status_code=400, detail=f"Unsupported tool type for try-run: {req.type}")

    adapter = HTTPToolAdapter(
        name=req.name,
        description=req.description or "Try-run HTTP tool",
        api_config=req.api_config,
        schema=req.json_schema or {},
        version=req.version,
    )

    # 準備請求摘要
    method = req.api_config.get("method", "GET").upper()
    url = req.api_config.get("url")
    headers = req.api_config.get("headers", {})

    t0 = time.time()
    result = adapter.invoke(**(req.params or {}))
    elapsed_ms = int((time.time() - t0) * 1000)

    # 嘗試擷取預覽資料
    preview = []
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, list):
            preview = data[:10]
        else:
            dt = result.get("datatable") if isinstance(result.get("datatable"), dict) else None
            if isinstance(dt, dict) and isinstance(dt.get("data"), list):
                preview = dt.get("data")[:10]

    ok = bool(preview)

    return {
        "ok": ok,
        "request": {
            "method": method,
            "url": url,
            "headers": headers,
            "params": req.params or {},
        },
        "response": result,
        "preview_rows": preview,
        "elapsed_ms": elapsed_ms,
        "error": None if ok else (result.get("error") if isinstance(result, dict) else "no previewable data"),
    }
