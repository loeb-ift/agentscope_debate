
import os
from api.database import Base, engine, SessionLocal
from api.init_data import initialize_all

# 1. 刪除舊資料庫檔案 (如果是 SQLite)
if os.path.exists("test.db"):
    os.remove("test.db")
    print("Deleted old database file.")

# 2. 創建所有表格
print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")

# 3. 初始化所有資料
print("Seeding data...")
db = SessionLocal()
try:
    initialize_all(db)
    print("Seeding complete.")
except Exception as e:
    print(f"Seeding failed: {e}")
finally:
    db.close()
