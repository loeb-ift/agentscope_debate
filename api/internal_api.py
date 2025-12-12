from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Optional, Dict
from api import schemas, financial_models
from api.database import SessionLocal
from api.config import Config
from pydantic import BaseModel
import os
from datetime import datetime
from functools import lru_cache
import time
import asyncio
from api.vector_store import VectorStore
import numpy as np

router = APIRouter(prefix="/api/v1/internal")

class SimilarityRequest(BaseModel):
    texts: List[str]

@router.post("/similarity")
async def calculate_similarity(req: SimilarityRequest):
    """
    計算文本列表的兩兩餘弦相似度矩陣。
    用於前端判斷專長是否過度重疊。
    """
    texts = [t.strip() for t in req.texts if t.strip()]
    if len(texts) < 2:
        return {"matrix": [[1.0]] if texts else []}
    
    embeddings = []
    for text in texts:
        emb = await VectorStore.get_embedding(text)
        if not emb:
            # Fallback for empty/failed embedding: zero vector
            emb = [0.0] * 768
        embeddings.append(emb)
    
    # Calculate Cosine Similarity Matrix
    # Sim(A, B) = dot(A, B) / (norm(A) * norm(B))
    matrix = []
    for i in range(len(embeddings)):
        row = []
        vec_a = np.array(embeddings[i])
        norm_a = np.linalg.norm(vec_a)
        
        for j in range(len(embeddings)):
            vec_b = np.array(embeddings[j])
            norm_b = np.linalg.norm(vec_b)
            
            if norm_a == 0 or norm_b == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
            row.append(similarity)
        matrix.append(row)
        
    return {"matrix": matrix}

# --- Caching Utils ---
# Simple TTL cache decorator could be added here if needed,
# but for now lru_cache is fine as data updates are manual via /update-from-web
_INDUSTRY_TREE_CACHE = {"data": None, "timestamp": 0}
CACHE_TTL = 300 # 5 minutes

class ConfigUpdate(BaseModel):
    key: str
    value: str

@router.post("/config")
def update_config(config: ConfigUpdate):
    Config.update(config.key, config.value)
    return {"status": "success", "key": config.key, "value": config.value}

@router.get("/config")
def get_config():
    """Return list of {key, value, description}"""
    configs = Config.get_all()
    result = []
    for k, v in configs.items():
        desc = Config.CONFIG_DESCRIPTIONS.get(k, "")
        result.append({"key": k, "value": str(v), "description": desc})
    # Sort for better UX (keys with description first, then alphabetical)
    result.sort(key=lambda x: (not x["description"], x["key"]))
    return result

@router.get("/companies/last-update")
def get_company_last_update():
    """Get the last update timestamp of company data"""
    last_update = Config.get("last_industry_chain_update")
    return {"last_update": last_update}

from fastapi import BackgroundTasks
import subprocess
import sys

def run_crawler_task():
    try:
        # Run the crawler script as a subprocess
        # Use sys.executable to ensure we use the same python interpreter
        result = subprocess.run(
            [sys.executable, "scripts/crawl_industry_chain.py"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": os.getcwd()}
        )
        if result.returncode == 0:
            Config.update("last_industry_chain_update", datetime.now().isoformat())
            print("Crawler task completed successfully.")
        else:
            print(f"Crawler task failed: {result.stderr}")
    except Exception as e:
        print(f"Error running crawler task: {e}")

@router.post("/companies/update-from-web")
def update_companies_from_web(background_tasks: BackgroundTasks):
    """Trigger background task to crawl and update company data from web"""
    # Invalidate cache
    _INDUSTRY_TREE_CACHE["data"] = None
    background_tasks.add_task(run_crawler_task)
    return {"status": "started", "message": "Crawler task started in background."}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper for Generic CRUD ---
def generic_list(db: Session, model: Any, skip: int, limit: int):
    return db.query(model).offset(skip).limit(limit).all()

def generic_create(db: Session, model: Any, data: dict):
    db_obj = model(**data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def generic_get(db: Session, model: Any, id_field: str, id_value: str):
    return db.query(model).filter(getattr(model, id_field) == id_value).first()

# --- 1. Companies ---
@router.get("/companies", response_model=List[schemas.Company])
def list_companies(
    skip: int = 0,
    limit: int = 100,
    sector: Optional[str] = None,
    group: Optional[str] = None,
    sub_industry: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(financial_models.Company)
    if sector:
        query = query.filter(financial_models.Company.industry_sector == sector)
    if group:
        query = query.filter(financial_models.Company.industry_group.like(f"%{group}%"))
    if sub_industry:
        query = query.filter(financial_models.Company.sub_industry.like(f"%{sub_industry}%"))
        
    return query.offset(skip).limit(limit).all()

@router.get("/industry-tree")
def get_industry_tree(db: Session = Depends(get_db)):
    """返回產業鏈樹狀結構：Sector -> Group (Stream) -> Sub-industry -> Companies"""
    # Check cache
    now = time.time()
    if _INDUSTRY_TREE_CACHE["data"] and (now - _INDUSTRY_TREE_CACHE["timestamp"] < CACHE_TTL):
        return _INDUSTRY_TREE_CACHE["data"]

    companies = db.query(financial_models.Company).all()
    tree = {}
    for c in companies:
        sector = c.industry_sector or "未分類"
        # group might be "上游; 中游", so split
        groups = (c.industry_group or "未分類").split(';')
        
        if sector not in tree: tree[sector] = {}
        
        for g in groups:
            g = g.strip()
            if not g: continue
            if g not in tree[sector]: tree[sector][g] = []
            
            tree[sector][g].append({
                "id": c.company_id,
                "name": c.company_name,
                "ticker": c.ticker_symbol,
                "sub_industry": c.sub_industry
            })
    
    # Update cache
    _INDUSTRY_TREE_CACHE["data"] = tree
    _INDUSTRY_TREE_CACHE["timestamp"] = now
    return tree

@router.get("/sectors", response_model=List[str])
def list_sectors(db: Session = Depends(get_db)):
    """返回所有不重複的產業類別"""
    # Use simple caching for sectors too if needed, but it's fast enough usually.
    # We can reuse the tree structure to get keys if we wanted to be consistent.
    result = db.query(financial_models.Company.industry_sector).distinct().all()
    return [r[0] for r in result if r[0]]

@router.post("/companies", response_model=schemas.Company, status_code=201)
def create_company(company: schemas.CompanyCreate, db: Session = Depends(get_db)):
    return generic_create(db, financial_models.Company, company.dict())

@router.get("/companies/{company_id}", response_model=schemas.Company)
def get_company(company_id: str, db: Session = Depends(get_db)):
    obj = generic_get(db, financial_models.Company, 'company_id', company_id)
    if not obj: raise HTTPException(404, "Company not found")
    return obj

# --- 2. Securities ---

@router.get("/securities", response_model=List[schemas.Security])
def list_securities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.Security, skip, limit)

@router.post("/securities", response_model=schemas.Security, status_code=201)
def create_security(security: schemas.SecurityCreate, db: Session = Depends(get_db)):
    return generic_create(db, financial_models.Security, security.dict())

# --- 3. Financial Institutions ---
@router.get("/financial_institutions")
def list_institutions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.FinancialInstitution, skip, limit)

# --- 4. Exchanges ---
@router.get("/exchanges")
def list_exchanges(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.Exchange, skip, limit)

# --- 5. Key Personnel ---
@router.get("/key_personnel")
def list_key_personnel(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.KeyPersonnel, skip, limit)

# --- 6. Financial Terms ---
@router.get("/financial_terms", response_model=List[schemas.FinancialTerm])
def list_financial_terms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.FinancialTerm, skip, limit)

@router.put("/financial_terms/{term_id}", response_model=schemas.FinancialTerm)
def update_financial_term(term_id: str, term_update: schemas.FinancialTermUpdate, db: Session = Depends(get_db)):
    db_term = db.query(financial_models.FinancialTerm).filter(financial_models.FinancialTerm.term_id == term_id).first()
    if not db_term:
        raise HTTPException(status_code=404, detail="Financial Term not found")
    
    update_data = term_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_term, field, value)
    
    db.commit()
    db.refresh(db_term)
    return db_term

# --- 7. Corporate Relationships ---
@router.get("/corporate_relationships")
def list_corporate_relationships(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.CorporateRelationship, skip, limit)