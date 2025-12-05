from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 使用環境變數或預設路徑
db_path = os.getenv('DATABASE_URL', 'sqlite:///./data/debate.db')
SQLALCHEMY_DATABASE_URL = db_path

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """初始化資料庫，創建所有表"""
    # 導入所有 models 以確保它們被註冊
    from api import models
    
    # 使用 models.Base 而不是本地 Base
    models.Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")
