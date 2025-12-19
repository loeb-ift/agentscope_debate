import sys
import os
import json
sys.path.append(os.getcwd())

from worker.utils.price_proof_coordinator import get_price_proof, TEJClient, asdict

def test_proof():
    print("Running Price Proof Verification...")
    symbol = "2330.TW"
    date_str = "2024-11-01"
    
    # Try with TEJ (might fail if no key, but logic handles it)
    try:
        tej = TEJClient()
    except Exception as e:
        print(f"TEJ Client init warning: {e}")
        tej = None

    proof = get_price_proof(symbol, date_str, tej_client=tej)
    
    print(f"Success: {proof.success}")
    print(f"Source: {proof.source}")
    print(f"Trade Date: {proof.trade_date}")
    
    if proof.row:
        print(f"Price: {proof.row.close}")
    
    if proof.warnings:
        print("Warnings:", proof.warnings)
        
    if proof.cross_checks:
        print("Cross Checks:", json.dumps(proof.cross_checks, indent=2, default=str))

if __name__ == "__main__":
    test_proof()