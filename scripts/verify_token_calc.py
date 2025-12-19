import tiktoken
from api.cost_utils import CostService

def verify_token_calculation():
    print("=== Verifying Token Calculation Accuracy ===\n")
    
    test_cases = [
        "Hello, world!",
        "你好，世界！",  # Chinese
        "Python is awesome.",
        "      ",  # Whitespace
        "",  # Empty
        "A" * 100,  # Repeated char
    ]
    
    # Ground Truth using tiktoken directly
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        print(f"Error loading tiktoken for verification: {e}")
        return

    print(f"{'Text Content':<30} | {'Expected':<10} | {'Calculated':<10} | {'Result'}")
    print("-" * 70)

    for text in test_cases:
        expected = len(enc.encode(text))
        calculated = CostService.calculate_tokens(text)
        
        display_text = text if len(text) < 25 else text[:25] + "..."
        if not text: display_text = "(Empty)"
        
        status = "✅ PASS" if expected == calculated else "❌ FAIL"
        
        print(f"{display_text:<30} | {expected:<10} | {calculated:<10} | {status}")

    print("\n=== End Verification ===")

if __name__ == "__main__":
    verify_token_calculation()