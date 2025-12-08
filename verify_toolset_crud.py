import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

def print_response(response):
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response Body: {response.text}")
    print("-" * 20)

def verify_toolset_crud():
    print("=== Starting Toolset CRUD Verification ===\n")

    # 1. Create a Test Toolset
    print("1. Creating Test Toolset...")
    toolset_data = {
        "name": "Test Toolset for CRUD",
        "description": "A toolset created for testing CRUD operations",
        "tool_names": ["searxng.search"],
        "is_global": False
    }
    
    response = requests.post(f"{BASE_URL}/toolsets", json=toolset_data)
    print_response(response)
    
    if response.status_code != 201:
        print("Failed to create toolset. Exiting.")
        return

    toolset_id = response.json()["id"]
    print(f"Created Toolset ID: {toolset_id}\n")

    # 2. Get Toolset Details (Read)
    print(f"2. Getting Toolset Details for ID: {toolset_id}...")
    response = requests.get(f"{BASE_URL}/toolsets/{toolset_id}")
    print_response(response)
    
    if response.status_code != 200:
        print("Failed to get toolset details. Exiting.")
        return

    # 3. Update Toolset
    print(f"3. Updating Toolset ID: {toolset_id}...")
    update_data = {
        "name": "Updated Test Toolset Name",
        "description": "Updated description",
        "tool_names": ["searxng.search", "tej.stock_price"]
    }
    
    response = requests.put(f"{BASE_URL}/toolsets/{toolset_id}", json=update_data)
    print_response(response)
    
    if response.status_code != 200:
        print("Failed to update toolset. Exiting.")
        return
        
    # Verify update
    updated_toolset = response.json()
    if updated_toolset["name"] != update_data["name"] or \
       updated_toolset["description"] != update_data["description"] or \
       len(updated_toolset["tool_names"]) != 2:
        print("Update verification failed!")
    else:
        print("Update verified successfully.\n")

    # 4. List Toolsets
    print("4. Listing all toolsets...")
    response = requests.get(f"{BASE_URL}/toolsets")
    # print_response(response) # Don't print full list to avoid clutter
    print(f"Status Code: {response.status_code}")
    
    found = False
    for ts in response.json():
        if ts["id"] == toolset_id:
            found = True
            print(f"Found created toolset in list: {ts['name']}")
            break
    
    if not found:
        print("Created toolset NOT found in list!")
    else:
        print("List verification successful.\n")

    # 5. Delete Toolset
    print(f"5. Deleting Toolset ID: {toolset_id}...")
    response = requests.delete(f"{BASE_URL}/toolsets/{toolset_id}")
    print(f"Status Code: {response.status_code}")
    print("-" * 20)
    
    if response.status_code != 204:
        print("Failed to delete toolset.")
    else:
        print("Delete request successful.\n")

    # 6. Verify Deletion
    print(f"6. Verifying Deletion of ID: {toolset_id}...")
    response = requests.get(f"{BASE_URL}/toolsets/{toolset_id}")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 404:
        print("Verification successful: Toolset not found.")
    else:
        print("Verification failed: Toolset still exists.")

    print("\n=== Toolset CRUD Verification Complete ===")

if __name__ == "__main__":
    try:
        verify_toolset_crud()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Make sure the server is running on localhost:8002")
