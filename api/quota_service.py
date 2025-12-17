
import datetime
from api.redis_client import get_redis_client
from api.config import Config

class QuotaService:
    def __init__(self):
        try:
            self.redis = get_redis_client()
        except:
            self.redis = None
            print("⚠️ QuotaService: Redis not available. Quota checks will always pass (fallback).")
            
        self.limit = getattr(Config, "SEARCH_PAID_DAILY_LIMIT", 50)

    def _get_key(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        return f"quota:search:paid:{today}"

    def check_quota(self) -> bool:
        """Check if quota is available."""
        if not self.redis:
            return True # Fail open if Redis is down
            
        key = self._get_key()
        try:
            count = self.redis.get(key)
            if count and int(count) >= self.limit:
                return False
            return True
        except Exception as e:
            print(f"Error checking quota: {e}")
            return True

    def increment(self):
        """Increment usage count."""
        if not self.redis:
            return
            
        key = self._get_key()
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 86400 * 2) # Keep for 48h just in case
            pipe.execute()
        except Exception as e:
            print(f"Error incrementing quota: {e}")

    def get_usage(self) -> dict:
        """Get current usage stats."""
        if not self.redis:
            return {"used": 0, "limit": self.limit, "remaining": self.limit}
            
        key = self._get_key()
        try:
            count = self.redis.get(key)
            used = int(count) if count else 0
            return {
                "used": used,
                "limit": self.limit,
                "remaining": max(0, self.limit - used)
            }
        except:
            return {"used": 0, "limit": self.limit, "remaining": self.limit}

quota_service = QuotaService()
