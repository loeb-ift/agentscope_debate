"""
資料庫遷移腳本：更新 Agent 表結構
添加 role, specialty, updated_at 欄位
將 id 從 Integer 改為 String(UUID)
"""

import sqlite3
import os

def migrate_agents_table():
    db_path = os.getenv('DATABASE_URL', 'sqlite:///./debate.db').replace('sqlite:///', '')
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 創建新的 agents 表（帶有新結構）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'debater',
                specialty TEXT,
                system_prompt TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 檢查舊表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
        old_table_exists = cursor.fetchone() is not None
        
        if old_table_exists:
            # 3. 遷移舊數據到新表
            print("Migrating existing data...")
            cursor.execute("""
                INSERT INTO agents_new (id, name, role, specialty, system_prompt, config_json, created_at, updated_at)
                SELECT 
                    CAST(id AS TEXT),
                    name,
                    'debater' as role,
                    NULL as specialty,
                    system_prompt,
                    config_json,
                    created_at,
                    created_at as updated_at
                FROM agents
            """)
            
            # 4. 刪除舊表
            cursor.execute("DROP TABLE agents")
        
        # 5. 重命名新表
        cursor.execute("ALTER TABLE agents_new RENAME TO agents")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_agents_table()
