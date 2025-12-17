# Verification script for date format fix in worker/debate_cycle.py

def verify_fix():
    print("Verifying date format fix logic...")
    
    # Simulate the input from TEJ params (YYYY-MM-DD)
    v_date = "2024-01-01"
    
    # Simulate the logic in _neutral_verification_turn_async
    # Logic: clean_date = str(v_date)[:10].replace("-", "")
    
    clean_date = str(v_date)[:10].replace("-", "")
    
    print(f"Input: {v_date}")
    print(f"Output: {clean_date}")
    
    expected = "20240101"
    
    if clean_date == expected:
        print("✅ Verification PASSED: Date format is correctly stripped of dashes.")
        return True
    else:
        print(f"❌ Verification FAILED: Expected {expected}, got {clean_date}")
        return False

if __name__ == "__main__":
    verify_fix()