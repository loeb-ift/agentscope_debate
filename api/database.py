from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 使用環境變數或預設路徑
db_path = os.getenv('DATABASE_URL', 'sqlite:///./data/debate.db')
SQLALCHEMY_DATABASE_URL = db_path

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,        # Base number of connections
    max_overflow=20,     # Max extra connections
    pool_recycle=1800,   # Recycle connections after 30 mins
    pool_timeout=30      # Wait 30s for a connection
)

# Enable WAL mode for better concurrency
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    獲取資料庫 session 的相依性函數。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()

def init_db():
    """初始化資料庫，創建所有表"""
    # 導入所有 models 以確保它們被註冊
    from api import models
    
    # 使用 models.Base 而不是本地 Base
    models.Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")
