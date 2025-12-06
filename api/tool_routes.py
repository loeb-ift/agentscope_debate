from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from api import schemas, models
from api.database import SessionLocal
from api.tool_registry import tool_registry
from adapters.http_tool_adapter import HTTPToolAdapter
from adapters.python_tool_adapter import PythonToolAdapter
from worker.llm_utils import call_llm
from api.prompt_service import PromptService

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/v1/tools", response_model=List[schemas.Tool])
def list_tools(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """列出所有資料庫中的自定義工具"""
    return db.query(models.Tool).offset(skip).limit(limit).all()

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
                description="User defined HTTP tool",
                api_config=db_tool.api_config,
                schema=db_tool.json_schema
            )
        elif db_tool.type == "python":
            adapter = PythonToolAdapter(
                name=db_tool.name,
                description="User defined Python tool",
                python_code=db_tool.python_code,
                schema=db_tool.json_schema
            )
            
        if adapter:
            tool_registry.register(adapter, group=db_tool.group)
        
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