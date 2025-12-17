import requests
import time
import sys

BASE_URL = "http://localhost:8000/api/v2"
TOPIC = "敦陽科(2480.TW) 為什麼一直下跌"

def run_test():
    print(f"🚀 Starting MARS V2 Verification for topic: {TOPIC}")
    
    # 1. Start Research
    try:
        resp = requests.post(f"{BASE_URL}/research", json={"topic": TOPIC})
        resp.raise_for_status()
        data = resp.json()
        task_id = data["task_id"]
        print(f"✅ Task submitted. ID: {task_id}")
    except Exception as e:
        print(f"❌ Failed to submit task: {e}")
        sys.exit(1)
        
    # 2. Poll Status
    max_retries = 60 # 60 seconds
    for i in range(max_retries):
        try:
            status_resp = requests.get(f"{BASE_URL}/research/{task_id}")
            status_data = status_resp.json()
            status = status_data.get("status")
            
            print(f"⏳ Polling status: {status} ({i+1}/{max_retries})")
            
            if status == "completed":
                print("\n✅ Task Completed!")
                artifacts = status_data.get("artifacts", [])
                print(f"📦 Artifacts Generated: {len(artifacts)}")
                
                for idx, art in enumerate(artifacts):
                    print(f"\n--- Artifact {idx+1} ---")
                    print(f"ID: {art.get('id')}")
                    print(f"Type: {art.get('type')}")
                    content = art.get('content')
                    # Truncate content for display
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"Content: {preview}")
                    print(f"Metadata: {art.get('metadata')}")
                
                break
            
            if status == "failed":
                print(f"\n❌ Task Failed!")
                # Try to fetch error details if possible
                error_msg = requests.get(f"{BASE_URL}/research/{task_id}").json().get("error")
                if not error_msg:
                    # If API doesn't return error directly, we might need to enhance API or guess.
                    pass
                print(f"Reason: {error_msg}")
                break
                
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ Error polling status: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_test()