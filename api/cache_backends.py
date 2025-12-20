import json
from typing import Optional
from api.redis_client import get_redis_client

class MemoryCache:
    def __init__(self):
        self._store = {}
    def get(self, key: str):
        return self._store.get(key)
    def set(self, key: str, value, ttl: Optional[int] = None):
        self._store[key] = value
    def delete(self, key: str):
        self._store.pop(key, None)

import os
class RedisCache:
    def __init__(self, key_prefix: str = None):
        self.r = get_redis_client()
        self.prefix = key_prefix or os.getenv("EFFECTIVE_TOOLS_PREFIX", "as:cache:")
    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"
    def get(self, key: str):
        raw = self.r.get(self._k(key))
        return json.loads(raw) if raw else None
    def set(self, key: str, value, ttl: Optional[int] = None):
        raw = json.dumps(value)
        if ttl:
            self.r.setex(self._k(key), ttl, raw)
        else:
            self.r.set(self._k(key), raw)
    def delete(self, key: str):
        self.r.delete(self._k(key))
