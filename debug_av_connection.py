
import httpx
import os
import asyncio

async def debug_connection():
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    url = f"https://mcp.alphavantage.co/mcp?apikey={api_key}"
    
    print(f"Connecting to: {url}")
    
    tests = [
        {"name": "Standard SSE", "headers": {"Accept": "text/event-stream"}},
        {"name": "No Headers", "headers": {}},
        {"name": "Explicit MCP Version", "headers": {"Accept": "text/event-stream", "mcp-version": "0.6"}}, # Trying to match server
        {"name": "Content-Type JSON (Weird)", "headers": {"Content-Type": "application/json"}},
    ]

    print("\n--- Testing Direct tools/list ---")
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            print(f"Status: {response.status_code}")
            print(f"Body: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")




if __name__ == "__main__":
    asyncio.run(debug_connection())
