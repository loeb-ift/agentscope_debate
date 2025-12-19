import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add current directory to sys.path
sys.path.append(os.getcwd())

from adapters.tej_adapter import TEJStockPrice

def main():
    print("Initializing TEJ Adapter...")
    adapter = TEJStockPrice()
    
    # Ensure API Key is present
    if not adapter.api_key:
        print("Error: TEJ_API_KEY not found in environment variables.")
        return

    db = os.getenv("TEJ_DATABASE_CODE", "TRAIL")
    coid = "2330"
    
    print(f"Target: {coid} in DB: {db}")
    
    # Helper to get value from row (handle list or dict)
    def get_val(row, key, idx):
        if isinstance(row, dict):
            return row.get(key)
        elif isinstance(row, list) and len(row) > idx:
            return row[idx]
        return None

    # TAPRCD Mapping (Based on observation): 0=coid, 1=mdate, 4=close_d? (Need to verify columns)
    # AIND Mapping: 0=coid, 1=cname?
    
    # 0. Check Company Info (AIND)
    print("\n--- Diagnostic: Check Company Info (AIND) ---")
    try:
        res_aind = adapter._execute_query(db, "AIND", params={"limit": 1}, filters={"coid": coid})
        rows_aind = res_aind.data.get("rows", [])
        if rows_aind:
             # AIND columns usually: coid, mdate, cname...
             print(f"Found 2330 in AIND. Row: {rows_aind[0]}")
        else:
             print("2330 NOT found in AIND.")
    except Exception as e:
        print(f"Error checking AIND: {e}")

    # 1. Probe Query (No date filters)
    print("\n--- Probe Query (Any data for 2330 in TAPRCD?) ---")
    try:
        probe_filters = {"coid": coid}
        res_probe = adapter._execute_query(
            db,
            "TAPRCD",
            params={"limit": 5},
            filters=probe_filters
        )
        rows_probe = res_probe.data.get("rows", [])
        if rows_probe:
            print(f"Probe Success! Found {len(rows_probe)} rows.")
            # Print first row to identify columns
            print(f"First Row Structure: {rows_probe[0]}")
            
            # Try to identify mdate index (likely looks like 'YYYY-MM-DD...')
            mdate_idx = -1
            for i, val in enumerate(rows_probe[0]):
                if isinstance(val, str) and "20" in val and "-" in val: # heuristics
                     mdate_idx = i
                     break
            print(f"Detected mdate index: {mdate_idx}")
            
            if mdate_idx != -1:
                print(f"Sample Dates: {[r[mdate_idx] for r in rows_probe]}")
        else:
            print("Probe Failed: No data found for 2330 in TAPRCD (TRAIL).")
    except Exception as e:
        print(f"Error during probe: {e}")

    # 2. Query latest date
    print("\n--- Querying Latest Date ---")
    try:
        latest_filters = {
            "coid": coid,
            "mdate.gte": "2024-01-01",
            "opts.sort": "mdate.desc",
        }
        
        res_latest = adapter._execute_query(
            db,
            "TAPRCD",
            params={"limit": 1},
            filters=latest_filters
        )
        
        rows = res_latest.data.get("rows", [])
        if rows:
            print(f"Latest Data Found: {rows[0]}")
        else:
            print("No latest data found with criteria.")
            
    except Exception as e:
        print(f"Error querying latest date: {e}")

    # 3. Query earliest date (Absolute)
    print("\n--- Querying Absolute Earliest Date (No pre-2000 filter) ---")
    try:
        # Just sort ascending to get the very first record
        earliest_filters = {
            "coid": coid,
            "opts.sort": "mdate.asc",
        }
        
        res_earliest = adapter._execute_query(
            db,
            "TAPRCD",
            params={"limit": 1},
            filters=earliest_filters
        )
        
        rows = res_earliest.data.get("rows", [])
        if rows:
            # mdate is index 1
            print(f"Absolute Earliest Data Found: {rows[0][1]} (Row: {rows[0]})")
        else:
            print("No data found at all for earliest query.")
                
    except Exception as e:
        print(f"Error querying earliest date: {e}")

if __name__ == "__main__":
    main()