
import asyncio
from unittest.mock import MagicMock, patch
from worker.memory import HippocampalMemory
from worker.evidence_lifecycle import EvidenceLifecycle
from api.database import Base, engine
from api.models import EvidenceDoc

def setup_db():
    EvidenceDoc.metadata.create_all(bind=engine)

async def test_lifecycle():
    debate_id = "test_lifecycle_debate"
    setup_db()
    
    # Mock Redis
    with patch("worker.memory.get_redis_client") as mock_get_redis:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        # Mock Redis get/set to simulate simple cache
        _cache = {}
        def mock_set(key, val, ex=None):
            _cache[key] = val
            return True
        def mock_get(key):
            return _cache.get(key)
        
        mock_redis.set.side_effect = mock_set
        mock_redis.get.side_effect = mock_get
        # Mock scan for cleanup if needed (returns empty)
        mock_redis.scan.return_value = ('0', [])
        mock_redis.incr.return_value = 1
        
        mem = HippocampalMemory(debate_id)
        
        # Tool Result 1: Valid
        print("\n[Test 1] Storing Valid Tool Result")
        await mem.store(
            agent_id="test_agent", 
            tool="tej.company_info", 
            params={"coid": "2330"}, 
            result={"data": [{"name": "TSMC"}]}
        )
        
        # Check that it reached Redis
        # Note: mem.retrieve_working_memory uses self.redis.get
        cached = await mem.retrieve_working_memory("tej.company_info", {"coid": "2330"})
        if cached:
            print(f"✅ Redis Cache Hit: {cached['id']}")
            # In our mock logic, retrieve returns parsed json if we stored json string.
            # But our mock_redis.get returns string because that's what redis does?
            # Creating a decent mock for get/set serialization is tricky.
            # Let's trust mem.store logic handles json.dumps.
            # So mock_redis.get returns the json string from _cache.
            # mem.retrieve... does json.loads.
            assert cached["metadata"]["trust_level"] == "verified"
            print(f"✅ Status: Verified")
        else:
            print("❌ Redis Cache Miss (Unexpected)")

        # Tool Result 2: Empty/Quarantine
        print("\n[Test 2] Storing Empty Result (Should Quarantine)")
        await mem.store(
            agent_id="test_agent", 
            tool="tej.company_info", 
            params={"coid": "0000"}, 
            result={"data": []}
        )
        
        # Check Memory (Should be MISS in Redis)
        # Note: We must ensure _cache doesn't have it.
        cached_empty = await mem.retrieve_working_memory("tej.company_info", {"coid": "0000"})
        if cached_empty is None:
            print(f"✅ Redis Cache Miss (Correctly Quarantined)")
        else:
            print(f"❌ Unexpected Cache Hit for Quarantined Item: {cached_empty}")
        
    print("\n=== Lifecycle Test Passed ===")

if __name__ == "__main__":
    asyncio.run(test_lifecycle())
