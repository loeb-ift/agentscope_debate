import asyncio
import os
import time
from api.config import Config
from worker.llm_utils import call_llm_async, get_llm_provider
from api.vector_store import VectorStore

async def test_provider(provider_name: str):
    print(f"\n{'='*40}")
    print(f"🔬 Testing Provider: {provider_name.upper()}")
    print(f"{'='*40}")
    
    # 1. Backup & Switch Config
    original_provider = Config.LLM_PROVIDER
    original_emb_provider = getattr(Config, "EMBEDDING_PROVIDER", "")
    
    Config.LLM_PROVIDER = provider_name
    Config.EMBEDDING_PROVIDER = "" # Force auto-sync
    
    try:
        # 2. Print Target Config
        if provider_name == "azure_openai":
            print(f"Target Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
            print(f"Target Model: {Config.AZURE_OPENAI_MODEL_DEPLOYMENT}")
        elif provider_name == "ollama":
            print(f"Target Host: {Config.OLLAMA_HOST}")
            print(f"Target Model: {Config.OLLAMA_MODEL}")
            
        # 3. Test LLM Chat
        print("\n--- [LLM Chat Test] ---")
        try:
            prompt = f"Are you {provider_name}?"
            print(f"Sending prompt: '{prompt}'")
            
            # Use unique context tag to bypass cache
            tag = f"verify_{provider_name}_{time.time()}"
            response = await call_llm_async(prompt, context_tag=tag)
            
            print(f"Response: '{response}'")
            
            if "Error:" in response or not response:
                print("❌ Chat Verification Failed.")
            else:
                print("✅ Chat Verification Successful!")
                
        except Exception as e:
            print(f"❌ Chat Exception: {e}")

        # 4. Test Embedding
        print("\n--- [Embedding Test] ---")
        try:
            text = f"Testing embedding for {provider_name}"
            print(f"Generating embedding for: '{text}'")
            
            # VectorStore uses Config directly, so our switch should work
            emb = await VectorStore.get_embedding(text)
            
            if emb and len(emb) > 0:
                 print(f"✅ Embedding Successful! Vector size: {len(emb)}")
                 if provider_name == "ollama" and len(emb) == 768:
                     print("ℹ️  Size matches standard Ollama/Nomic (768)")
                 elif provider_name == "azure_openai" and len(emb) == 1536:
                     print("ℹ️  Size matches standard OpenAI (1536)")
            else:
                 print("❌ Embedding Failed: Empty result")
                 
        except Exception as e:
            print(f"❌ Embedding Exception: {e}")
            
    finally:
        # Restore Config
        Config.LLM_PROVIDER = original_provider
        Config.EMBEDDING_PROVIDER = original_emb_provider
        print("\n(Config restored)")

async def main():
    print("🚀 Starting Comprehensive Model Verification...")
    
    # Test Azure
    await test_provider("azure_openai")
    
    # Test Ollama
    await test_provider("ollama")
    
    print("\n🏁 All tests completed.")

if __name__ == "__main__":
    asyncio.run(main())