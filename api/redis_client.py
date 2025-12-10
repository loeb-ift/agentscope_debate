import redis
import os

class RedisClient:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            redis_url = os.getenv('REDIS_URL')
            
            if redis_url:
                cls._pool = redis.ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    max_connections=20
                )
            else:
                redis_host = os.getenv('REDIS_HOST', 'redis')
                redis_port = int(os.getenv('REDIS_PORT', 6379))
                redis_db = int(os.getenv('REDIS_DB', 0))
                
                cls._pool = redis.ConnectionPool(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    max_connections=20
                )
        return cls._pool

    @classmethod
    def get_client(cls):
        return redis.Redis(connection_pool=cls.get_pool())

# Singleton instance accessor
def get_redis_client():
    return RedisClient.get_client()