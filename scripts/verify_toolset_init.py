from api.database import SessionLocal
from api.init_data import initialize_toolsets
from api import models

def verify_toolsets():
    db = SessionLocal()
    try:
        print("Initializing toolsets to apply updates...")
        initialize_toolsets(db)
        
        print("\nVerifying ToolSet descriptions...")
        toolsets = db.query(models.ToolSet).all()
        for ts in toolsets:
            print(f"[{ts.name}]")
            print(f"  Description: {ts.description}")
            print(f"  Tools count: {len(ts.tool_names)}")
            print("-" * 30)
            
    finally:
        db.close()

if __name__ == "__main__":
    verify_toolsets()
