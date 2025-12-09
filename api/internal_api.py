from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any
from api import schemas, financial_models
from api.database import SessionLocal
from api.config import Config
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/internal")

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
def list_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return generic_list(db, financial_models.Company, skip, limit)

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