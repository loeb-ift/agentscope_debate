import asyncio
import os
import sys
import json
from api.vector_store import VectorStore

async def main():
    print("=== 🔍 Inspecting Semantic Cache ===")
    collection_name = "llm_semantic_cache"
    
    try:
        # We need to access the client directly for scroll, or add scroll to VectorStore.
        # VectorStore.get_client() returns the sync QdrantClient (or whatever is configured).
        # But wait, api/vector_store.py uses QdrantClient (Sync).
        # So we can use it.
        
        client = VectorStore.get_client()
        
        # Check if collection exists
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            print(f"❌ Collection '{collection_name}' does not exist.")
            return

        # Scroll (Pagination)
        # Note: qdrant-client v1.x uses scroll()
        # limit=100
        response = client.scroll(
            collection_name=collection_name,
            limit=50,
            with_payload=True,
            with_vectors=False
        )
        
        points = response[0] # (points, next_page_offset)
        
        print(f"Found {len(points)} entries in cache.\n")
        
        for p in points:
            payload = p.payload
            resp_text = payload.get('response', '')
            timestamp = payload.get('timestamp', 'N/A')
            context = payload.get('context', 'None')
            
            print(f"ID: {p.id}")
            print(f"Context: {context}")
            print(f"Time: {timestamp}")
            print(f"Response Preview: {resp_text[:100]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error inspecting cache: {e}")

if __name__ == "__main__":
    asyncio.run(main())