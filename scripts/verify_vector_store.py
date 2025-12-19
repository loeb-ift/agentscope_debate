import asyncio
import os
from api.vector_store import VectorStore
from api.config import Config

async def main():
    print("=== Testing VectorStore Integration ===")
    print(f"Qdrant URL: {Config.QDRANT_URL}")
    print(f"Embedding Host: {Config.OLLAMA_EMBEDDING_HOST}")
    print(f"Embedding Model: {Config.OLLAMA_EMBEDDING_MODEL}")
    
    collection_name = "test_collection_v1"
    
    # 1. Test Embedding Generation
    print("\n[1] Testing Embedding Generation...")
    try:
        text = "Hello, World!"
        embedding = await VectorStore.get_embedding(text)
        if embedding and len(embedding) > 0:
            print(f"✅ Embedding success. Vector size: {len(embedding)}")
        else:
            print("❌ Embedding failed (empty result).")
    except Exception as e:
        print(f"❌ Embedding exception: {e}")
        return

    # 2. Test Adding Vectors
    print("\n[2] Testing Add Vectors (Upsert)...")
    try:
        texts = ["Apple is a fruit", "Tesla is a car"]
        metadatas = [{"category": "fruit"}, {"category": "car"}]
        await VectorStore.add_texts(collection_name, texts, metadatas)
        print("✅ Add texts call completed.")
    except Exception as e:
        print(f"❌ Add texts exception: {e}")
        return

    # 3. Test Searching
    print("\n[3] Testing Search...")
    try:
        query = "fruit"
        results = await VectorStore.search(collection_name, query, limit=1)
        print(f"Search results: {results}")
        
        if results and "Apple" in results[0].get('text', ''):
            print("✅ Search verification passed (Found 'Apple').")
        else:
            print(f"⚠️ Search verification warning: Expected 'Apple', got {results}")
            
    except Exception as e:
        print(f"❌ Search exception: {e}")

    # 4. Test Filtering
    print("\n[4] Testing Filtered Search...")
    try:
        query = "vehicle" # Semantic match for car
        filter_cond = {"category": "car"}
        results = await VectorStore.search(collection_name, query, limit=1, filter_conditions=filter_cond)
        print(f"Filtered results: {results}")
        
        if results and "Tesla" in results[0].get('text', ''):
            print("✅ Filter verification passed (Found 'Tesla').")
        else:
            print(f"⚠️ Filter verification warning: Expected 'Tesla', got {results}")
            
    except Exception as e:
        print(f"❌ Filter search exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())