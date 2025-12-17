import asyncio
import os
from api.config import Config
from worker.llm_utils import call_llm_async, get_llm_provider
from api.vector_store import VectorStore

async def verify_llm():
    print("=== LLM Configuration Verification ===")
    
    # 1. Print Current Config
    print(f"Provider: {Config.LLM_PROVIDER}")
    
    if Config.LLM_PROVIDER == "ollama":
        print(f"Host: {Config.OLLAMA_HOST}")
        print(f"Model: {Config.OLLAMA_MODEL}")
    elif Config.LLM_PROVIDER == "azure_openai":
        print(f"Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
        print(f"Deployment: {Config.AZURE_OPENAI_MODEL_DEPLOYMENT}")
        print(f"API Version: {getattr(Config, 'AZURE_OPENAI_API_VERSION', 'Unknown')}")
        # Mask API Key
        key = Config.AZURE_OPENAI_API_KEY
        masked_key = f"{key[:4]}...{key[-4:]}" if key and len(key) > 8 else "***"
        print(f"API Key: {masked_key}")
    elif Config.LLM_PROVIDER == "openai":
        print(f"Base URL: {getattr(Config, 'OPENAI_BASE_URL', 'Default')}")
        print(f"Model: {getattr(Config, 'OPENAI_MODEL', 'gpt-4')}")
        
    print("\n--- Testing Connectivity ---")
    
    try:
        # 2. Test Call
        prompt = "Hello! Are you working?"
        print(f"Sending prompt: '{prompt}'")
        
        # Force skip cache to test real connection
        import time
        response = await call_llm_async(prompt, context_tag=f"verify_{time.time()}")
        
        print(f"\nResponse received:")
        print(f"'{response}'")
        
        if "Error:" in response:
            print("\n❌ LLM Verification Failed.")
        else:
            print("\n✅ LLM Verification Successful!")
            
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")

    print("\n--- Testing Embedding ---")
    try:
        text = "Hello Embedding"
        print(f"Generating embedding for: '{text}'")
        emb = await VectorStore.get_embedding(text)
        
        if emb and len(emb) > 0:
             print(f"✅ Embedding Successful! Vector size: {len(emb)}")
        else:
             print("❌ Embedding Failed: Empty result")
             
    except Exception as e:
        print(f"❌ Embedding Exception: {e}")

if __name__ == "__main__":
    asyncio.run(verify_llm())