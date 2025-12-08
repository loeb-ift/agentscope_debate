import sqlite3
import csv
import os

def verify_companies():
    # 1. Read Source Data
    source_codes = set()
    file_path = '公司實體名冊.txt'
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print(f"Reading {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            reader = csv.reader(lines)
            
            # Skip header if it exists
            # The first line usually contains "出表日期,公司代號,..."
            header_row = next(reader, None)
            
            for row in reader:
                if len(row) >= 2:
                    # Column 1 is company code (0-indexed)
                    code = row[1].strip()
                    # Basic validation: ensure it's not empty
                    if code:
                        source_codes.add(code)
    except Exception as e:
        print(f"Error reading source file: {e}")
        return

    print(f"Found {len(source_codes)} unique company codes in source file.")

    # 2. Read Database Data
    db_path = 'data/debate.db'
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} not found.")
        return

    print(f"Connecting to database {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    db_codes = set()
    
    try:
        # Check table existence
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies';")
        if not cursor.fetchone():
             print("Error: Table 'companies' does not exist in the database.")
             # List existing tables to be helpful
             cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
             tables = cursor.fetchall()
             print(f"Existing tables: {[t[0] for t in tables]}")
             return

        # Inspect columns to find the company code column
        cursor.execute("PRAGMA table_info(companies)")
        columns_info = cursor.fetchall()
        columns = [info[1] for info in columns_info]
        print(f"Table 'companies' columns: {columns}")
        
        # Heuristic to find the code column
        target_col = None
        candidates = ['id', 'code', 'stock_id', 'company_code', 'symbol']
        
        for cand in candidates:
            if cand in columns:
                target_col = cand
                break
        
        if not target_col:
            # If no obvious candidate, assume the first column is the primary key/code
            if columns:
                target_col = columns[0]
                print(f"Warning: Could not identify code column. Using first column '{target_col}' as code.")
            else:
                print("Error: Table has no columns.")
                return
        else:
            print(f"Using column '{target_col}' as company code.")

        cursor.execute(f"SELECT {target_col} FROM companies")
        rows = cursor.fetchall()
        for row in rows:
            if row[0]:
                # Normalize DB code: remove suffix like .TW if present
                code = str(row[0]).strip()
                if '.' in code:
                    code = code.split('.')[0]
                db_codes.add(code)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return
    finally:
        conn.close()

    print(f"Found {len(db_codes)} unique company codes in database.")

    # 3. Compare
    missing_in_db = source_codes - db_codes
    missing_in_file = db_codes - source_codes

    print("-" * 30)
    print("COMPARISON RESULTS")
    print("-" * 30)
    
    if not missing_in_db and not missing_in_file:
        print("SUCCESS: Database is fully synchronized with the source file. (100% match)")
    else:
        if missing_in_db:
            print(f"FAIL: Found {len(missing_in_db)} codes in file but MISSING from DB.")
            # Print first 10 missing codes
            missing_list = sorted(list(missing_in_db))
            print(f"Missing samples: {missing_list[:10]} ...")
            print("Full missing list:")
            print(missing_list)
        else:
            print("OK: All codes from file are present in DB.")

        if missing_in_file:
            print(f"NOTE: Found {len(missing_in_file)} codes in DB but not in file (extra data).")
            # Print first 10 extra codes
            extra_list = sorted(list(missing_in_file))
            print(f"Extra samples: {extra_list[:10]} ...")

if __name__ == "__main__":
    verify_companies()