import sys
import os
import asyncio
from datetime import datetime

# Ensure project root is in path
sys.path.append(os.getcwd())

from worker.utils.symbol_utils import normalize_symbol
from worker.utils.price_proof_coordinator import PriceProofCoordinator

def test_normalize():
    print("--- Testing normalize_symbol ---")
    # Test case 1: Pure number
    s1 = "5371"
    res1 = normalize_symbol(s1)
    print(f"normalize_symbol('{s1}'): {res1}")
    
    # Test case 2: With suffix
    s2 = "5371.TWO"
    res2 = normalize_symbol(s2)
    print(f"normalize_symbol('{s2}'): {res2}")
    print("-" * 30)

def test_price_coordinator():
    print("\n--- Testing PriceProofCoordinator ---")
    try:
        coordinator = PriceProofCoordinator()
    except Exception as e:
        print(f"Failed to initialize PriceProofCoordinator: {e}")
        return
    
    date = "2024-12-13" # 2024-12-13 is a Friday
    
    print(f"\n1. Testing get_verified_price('5371', date='{date}')")
    try:
        res1 = coordinator.get_verified_price("5371", date=date)
        print(f"Result: {res1}")
    except Exception as e:
        print(f"Error executing case 1: {e}")

    print(f"\n2. Testing get_verified_price('5371.TWO', date='{date}')")
    try:
        res2 = coordinator.get_verified_price("5371.TWO", date=date)
        print(f"Result: {res2}")
    except Exception as e:
        print(f"Error executing case 2: {e}")

if __name__ == "__main__":
    test_normalize()
    test_price_coordinator()