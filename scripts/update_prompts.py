from api.database import SessionLocal
from api.init_data import PromptService

def update_system_prompts():
    db = SessionLocal()
    try:
        print("Updating system prompts from YAML files...")
        PromptService.initialize_db_from_file(db)
        print("Prompts updated successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    update_system_prompts()