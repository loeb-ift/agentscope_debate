"""
Verify TEJ Tool Migration
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from api.database import SessionLocal
from api import models

def verify_migration():
    db = SessionLocal()
    try:
        tools = db.query(models.Tool).filter(models.Tool.provider == "tej").all()
        print(f"Total TEJ Tools: {len(tools)}")
        print("-" * 50)
        for tool in tools:
            print(f"- {tool.name}: {tool.description[:50]}...")
            if not tool.openapi_spec:
                print(f"  ❌ Missing OpenAPI Spec for {tool.name}")
            else:
                pass
                # print(f"  ✅ OpenAPI Spec Present")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_migration()