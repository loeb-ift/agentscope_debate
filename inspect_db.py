import sqlite3

def inspect_schema():
    conn = sqlite3.connect('data/debate.db')
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute("PRAGMA table_info(financial_terms)")
    columns = cursor.fetchall()
    
    print("Schema for 'financial_terms' table:")
    for col in columns:
        print(col)
        
    conn.close()

if __name__ == "__main__":
    inspect_schema()