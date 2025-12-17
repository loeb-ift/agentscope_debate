import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from api.database import SessionLocal
from api.prompt_service import PromptService

def refresh():
    print("🔄 Starting Prompt Refresh...")
    db = SessionLocal()
    try:
        # 1. Load defaults from YAML files
        print("   Loading prompts from files...")
        PromptService.load_defaults_from_file()
        
        # 2. Sync to Database
        print("   Syncing to database...")
        PromptService.initialize_db_from_file(db)
        
        print("✅ Prompt Refresh Completed Successfully.")
    except Exception as e:
        print(f"❌ Error refreshing prompts: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    refresh()