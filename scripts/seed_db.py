
from api.database import SessionLocal
from api.init_data import initialize_all

def seed_data():
    db = SessionLocal()
    try:
        initialize_all(db)
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
