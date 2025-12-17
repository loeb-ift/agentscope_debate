import os
import json
import httpx
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from api.config import Config

class EmbeddingProvider:
    async def get_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.host = Config.OLLAMA_EMBEDDING_HOST
        self.model = Config.OLLAMA_EMBEDDING_MODEL
        if not self.host.startswith(("http://", "https://")):
            self.host = f"http://{self.host}"

    async def get_embedding(self, text: str) -> List[float]:
        url = f"{self.host}/api/embeddings"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json={"model": self.model, "prompt": text})
                response.raise_for_status()
                data = response.json()
                return data["embedding"]
            except Exception as e:
                print(f"Error fetching embedding from Ollama: {e}")
                return []

class AzureEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.endpoint = Config.AZURE_OPENAI_ENDPOINT
        self.api_key = Config.AZURE_OPENAI_API_KEY
        self.deployment = getattr(Config, "AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
        self.api_version = getattr(Config, "AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
    def _get_url(self):
        base = self.endpoint.rstrip('/')
        return f"{base}/openai/deployments/{self.deployment}/embeddings?api-version={self.api_version}"

    async def get_embedding(self, text: str) -> List[float]:
        url = self._get_url()
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json={"input": text}, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
            except Exception as e:
                print(f"Error fetching embedding from Azure: {e}")
                return []

class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.base_url = getattr(Config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = getattr(Config, "OPENAI_API_KEY", "")
        self.model = getattr(Config, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    async def get_embedding(self, text: str) -> List[float]:
        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json={"input": text, "model": self.model}, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
            except Exception as e:
                print(f"Error fetching embedding from OpenAI: {e}")
                return []

def get_embedding_provider() -> EmbeddingProvider:
    # Use EMBEDDING_PROVIDER if set, otherwise fallback to LLM_PROVIDER
    # This ensures sync if user wants, but flexibility if set explicitly.
    provider_name = getattr(Config, "EMBEDDING_PROVIDER", "").lower()
    
    if not provider_name:
         provider_name = getattr(Config, "LLM_PROVIDER", "ollama").lower()
         
    if provider_name == "azure_openai":
        return AzureEmbeddingProvider()
    elif provider_name == "openai":
        return OpenAIEmbeddingProvider()
    else:
        return OllamaEmbeddingProvider()

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
        provider = get_embedding_provider()
        return await provider.get_embedding(text)

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
                if isinstance(value, dict) and any(k in value for k in ['gt', 'gte', 'lt', 'lte']):
                    must_clauses.append(qmodels.FieldCondition(key=key, range=qmodels.Range(**value)))
                elif isinstance(value, list):
                    for v in value:
                        should_clauses.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=v)))
                else:
                    must_clauses.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
            
            if should_clauses or must_clauses:
                query_filter = qmodels.Filter(must=must_clauses, should=should_clauses)

        # 3. Search (using query_points)
        client = cls.get_client()
        try:
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
        if not filter_conditions:
            return

        client = cls.get_client()
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