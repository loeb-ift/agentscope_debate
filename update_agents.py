from api.database import SessionLocal
from api.init_data import initialize_default_agents

def update_agents():
    db = SessionLocal()
    try:
        print("Updating agents from YAML files...")
        initialize_default_agents(db)
        print("Agents updated successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    update_agents()