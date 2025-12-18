
import os
import sqlite3

# 這次直接檢查 data/debate.db
DB_PATH = "data/debate.db"

def inspect_production_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ Production DB not found at {DB_PATH}")
        return

    print(f"\n--- Checking {DB_PATH} ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 檢查 tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        print(f"Tables: {table_names}")
        
        # 檢查 agents 數量
        if 'agents' in table_names:
            cursor.execute("SELECT count(*) FROM agents")
            count = cursor.fetchone()[0]
            print(f"Agents count: {count}")
            if count > 0:
                cursor.execute("SELECT name, role FROM agents LIMIT 5")
                print("   Sample agents:", cursor.fetchall())
        
        # 檢查 teams 數量
        if 'teams' in table_names:
            cursor.execute("SELECT count(*) FROM teams")
            count = cursor.fetchone()[0]
            print(f"Teams count: {count}")
            if count > 0:
                cursor.execute("SELECT name FROM teams LIMIT 5")
                print("   Sample teams:", cursor.fetchall())
                
        conn.close()
    except Exception as e:
        print(f"Error checking {DB_PATH}: {e}")

if __name__ == "__main__":
    inspect_production_db()
