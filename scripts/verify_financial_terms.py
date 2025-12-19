from api.database import SessionLocal
from api.financial_models import FinancialTerm
import sys

def verify_financial_terms():
    db = SessionLocal()
    try:
        print("Attempting to query FinancialTerm table...")
        # Try to select one to verify column mapping matches DB
        terms = db.query(FinancialTerm).limit(1).all()
        print(f"Successfully queried {len(terms)} terms.")
        
        # Check if we can access the 'meta' attribute (even if None)
        if terms:
            print(f"Term 1 meta: {terms[0].meta}")
        
        print("Verification SUCCESS: Schema matches Database.")
    except Exception as e:
        print(f"Verification FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    verify_financial_terms()