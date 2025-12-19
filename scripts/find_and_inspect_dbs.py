
import os
import sqlite3

def find_databases():
    # 搜尋當前目錄下的所有 .db 檔案
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    print(f"Found database files: {db_files}")
    
    for db_file in db_files:
        print(f"\n--- Checking {db_file} ---")
        try:
            conn = sqlite3.connect(db_file)
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
            
            # 檢查 teams 數量
            if 'teams' in table_names:
                cursor.execute("SELECT count(*) FROM teams")
                count = cursor.fetchone()[0]
                print(f"Teams count: {count}")
                
            conn.close()
        except Exception as e:
            print(f"Error checking {db_file}: {e}")

if __name__ == "__main__":
    find_databases()
