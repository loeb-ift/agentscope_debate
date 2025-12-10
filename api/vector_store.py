import os
import json
import httpx
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from api.config import Config

class VectorStore:
    _client = None
    
    @classmethod
    def get_client(cls):
        if cls._client is None:
            qdrant_url = Config.QDRANT_URL
            cls._client = QdrantClient(url=qdrant_url)
        return cls._client

    @classmethod
    def ensure_collection(cls, collection_name: str, vector_size: int = 768):
        client = cls.get_client()
        try:
            client.get_collection(collection_name)
        except Exception:
            # Collection does not exist, create it
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE)
            )

    @staticmethod
    async def get_embedding(text: str) -> List[float]:
        """Get embedding from Ollama (using dedicated embedding host)"""
        ollama_host = Config.OLLAMA_EMBEDDING_HOST
        model = Config.OLLAMA_EMBEDDING_MODEL
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{ollama_host}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                response.raise_for_status()
                data = response.json()
                return data["embedding"]
            except Exception as e:
                print(f"Error fetching embedding from {ollama_host}/api/embeddings: {e}")
                return []

    @classmethod
    async def add_texts(cls, collection_name: str, texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts:
            return
            
        # 1. Get Embeddings
        embeddings = []
        valid_texts = []
        valid_metadatas = []
        
        for i, text in enumerate(texts):
            emb = await cls.get_embedding(text)
            if emb:
                embeddings.append(emb)
                valid_texts.append(text)
                valid_metadatas.append(metadatas[i])
        
        if not embeddings:
            return

        # 2. Ensure Collection
        vector_size = len(embeddings[0])
        cls.ensure_collection(collection_name, vector_size)
        
        # 3. Upsert
        client = cls.get_client()
        points = []
        import uuid
        for i in range(len(embeddings)):
            points.append(qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload={"text": valid_texts[i], **valid_metadatas[i]}
            ))
            
        client.upsert(
            collection_name=collection_name,
            points=points
        )

    @classmethod
    async def search(cls, collection_name: str, query: str, limit: int = 3, filter_conditions: Dict = None) -> List[Dict[str, Any]]:
        # 1. Get Query Embedding
        query_vector = await cls.get_embedding(query)
        if not query_vector:
            return []
            
        # 2. Construct Filter
        query_filter = None
        if filter_conditions:
            should_clauses = []
            must_clauses = []
            for key, value in filter_conditions.items():
                if isinstance(value, list):
                    # Match any (Should)
                    for v in value:
                        should_clauses.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=v)))
                else:
                    # Match exact (Must)
                    must_clauses.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
            
            if should_clauses or must_clauses:
                query_filter = qmodels.Filter(must=must_clauses, should=should_clauses)

        # 3. Search (using query_points)
        client = cls.get_client()
        try:
            # Note: query_points is supported in newer qdrant-client versions
            # It replaces search/scroll/recommend with a unified API.
            results = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit
            ).points
            return [hit.payload for hit in results]
        except Exception as e:
            print(f"Search failed (collection might not exist): {e}")
            return []

    @classmethod
    async def delete_by_filter(cls, collection_name: str, filter_conditions: Dict[str, Any]):
        """
        Delete points matching the filter conditions.
        """
        if not filter_conditions:
            return

        client = cls.get_client()
        
        # Construct Filter
        must_clauses = []
        for key, value in filter_conditions.items():
            must_clauses.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
        
        query_filter = qmodels.Filter(must=must_clauses)
        
        try:
            client.delete(
                collection_name=collection_name,
                points_selector=qmodels.FilterSelector(filter=query_filter)
            )
            print(f"Deleted points in {collection_name} matching {filter_conditions}")
        except Exception as e:
            print(f"Delete failed: {e}")