import asyncio
import os
from unittest.mock import patch
import httpx

# Mock Config before importing worker.llm_utils if possible, 
# but since we are patching, we can do it inside the function.

async def reproduce_url_error():
    from worker.llm_utils import OllamaProvider

    print("--- Test Case 1: Host is empty string ---")
    with patch("worker.llm_utils.Config") as MockConfig:
        MockConfig.OLLAMA_HOST = ""
        MockConfig.OLLAMA_MODEL = "llama3"
        
        provider = OllamaProvider()
        print(f"OllamaProvider host: '{provider.host}'")
        
        # Test chat_completion
        messages = [{"role": "user", "content": "Hello"}]
        try:
            await provider.chat_completion(messages)
        except Exception as e:
            print(f"Caught expected exception: {e}")

    print("\n--- Test Case 2: Host is None ---")
    with patch("worker.llm_utils.Config") as MockConfig:
        MockConfig.OLLAMA_HOST = None
        MockConfig.OLLAMA_MODEL = "llama3"
        
        provider = OllamaProvider()
        print(f"OllamaProvider host: '{provider.host}'")
        
        try:
            await provider.chat_completion(messages)
        except Exception as e:
            print(f"Caught expected exception: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce_url_error())
