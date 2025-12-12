import json
import os
from api.database import SessionLocal
from api import financial_models
from decimal import Decimal
from datetime import date, datetime

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def dump_companies():
    db = SessionLocal()
    try:
        companies = db.query(financial_models.Company).all()
        data = []
        for c in companies:
            # Convert SQLAlchemy model to dict
            c_dict = {col.name: getattr(c, col.name) for col in c.__table__.columns}
            data.append(c_dict)
            
        output_path = "data/companies_seed.json"
        os.makedirs("data", exist_ok=True)
        
        output_data = {
            "meta": {
                "version": "1.0",
                "date": datetime.now().isoformat()
            },
            "data": data
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=json_serial)
            
        print(f"Successfully dumped {len(data)} companies to {output_path}")
        
    except Exception as e:
        print(f"Error dumping companies: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    dump_companies()