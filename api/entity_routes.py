from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from api import schemas, financial_models
from api.database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Company API ---

@router.get("/api/v1/entities/companies", response_model=List[schemas.Company])
def list_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(financial_models.Company).offset(skip).limit(limit).all()

@router.post("/api/v1/entities/companies", response_model=schemas.Company, status_code=201)
def create_company(company: schemas.CompanyCreate, db: Session = Depends(get_db)):
    db_company = financial_models.Company(**company.dict())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

@router.get("/api/v1/entities/companies/{company_id}", response_model=schemas.Company)
def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.query(financial_models.Company).filter(financial_models.Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company