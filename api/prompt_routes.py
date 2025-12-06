from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from api import schemas, models
from api.database import SessionLocal

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/v1/prompts", response_model=List[schemas.PromptTemplate])
def list_prompts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """列出所有 Prompt 模板"""
    return db.query(models.PromptTemplate).offset(skip).limit(limit).all()

@router.post("/api/v1/prompts", response_model=schemas.PromptTemplate, status_code=201)
def create_prompt(prompt: schemas.PromptTemplateCreate, db: Session = Depends(get_db)):
    """創建新的 Prompt 模板"""
    # 檢查 key 是否已存在
    existing = db.query(models.PromptTemplate).filter(
        models.PromptTemplate.key == prompt.key, 
        models.PromptTemplate.language == prompt.language
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Prompt with this key and language already exists")
    
    db_prompt = models.PromptTemplate(**prompt.dict())
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@router.put("/api/v1/prompts/{key}", response_model=schemas.PromptTemplate)
def update_prompt(key: str, update: schemas.PromptTemplateUpdate, language: str = "zh-TW", db: Session = Depends(get_db)):
    """更新 Prompt 模板"""
    db_prompt = db.query(models.PromptTemplate).filter(
        models.PromptTemplate.key == key,
        models.PromptTemplate.language == language
    ).first()
    
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if update.content:
        db_prompt.content = update.content
    if update.version:
        db_prompt.version = update.version
        
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@router.get("/api/v1/prompts/{key}", response_model=schemas.PromptTemplate)
def get_prompt(key: str, language: str = "zh-TW", db: Session = Depends(get_db)):
    """獲取單個 Prompt 模板"""
    db_prompt = db.query(models.PromptTemplate).filter(
        models.PromptTemplate.key == key,
        models.PromptTemplate.language == language
    ).first()
    
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    return db_prompt