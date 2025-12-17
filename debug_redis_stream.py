import redis
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Fallback for Docker environment if localhost fails
if REDIS_HOST == "redis":
    REDIS_HOST = "localhost"

print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    r.ping()
    print("✅ Redis Connected!")
except Exception as e:
    print(f"❌ Redis Connection Failed: {e}")
    sys.exit(1)

# List active keys to find recent debate
keys = r.keys("debate:*:topic")
print(f"\nFound {len(keys)} debate keys:")
latest_debate_id = None
for k in keys:
    # Key format: debate:{id}:topic
    parts = k.split(":")
    if len(parts) == 3:
        debate_id = parts[1]
        topic = r.get(k)
        print(f"- ID: {debate_id} | Topic: {topic}")
        latest_debate_id = debate_id

if not latest_debate_id:
    print("\n❌ No active debates found.")
    sys.exit(0)

print(f"\n🎧 Listening to stream for debate: {latest_debate_id}")
print(f"Channel: debate:{latest_debate_id}:log_stream")

pubsub = r.pubsub()
pubsub.subscribe(f"debate:{latest_debate_id}:log_stream")

print("\n--- Waiting for messages (Ctrl+C to stop) ---")

try:
    for message in pubsub.listen():
        if message['type'] == 'message':
            print(f"\n[Message Received]")
            try:
                data = json.loads(message['data'])
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(f"Raw Data: {message['data']}")
except KeyboardInterrupt:
    print("\nStopped.")