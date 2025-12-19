import sqlite3

def add_column():
    db_path = 'data/debate.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding 'meta' column to 'financial_terms' table...")
        # SQLite supports JSON, but it's stored as TEXT.
        cursor.execute("ALTER TABLE financial_terms ADD COLUMN meta JSON")
        conn.commit()
        print("Column added successfully.")
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")
        if "duplicate column name" in str(e):
            print("Column 'meta' might already exist.")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()