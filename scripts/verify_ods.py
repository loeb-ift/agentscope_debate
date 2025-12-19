import asyncio
import os
import shutil
from worker.data_scientist import DataScientistAgent
from adapters.docker_adapter import get_docker_adapter

async def test_ods_agent():
    print("🚀 Starting ODS Agent Test...")
    
    # 1. Test Docker Setup (Optional, mock if no docker)
    try:
        docker = get_docker_adapter()
        # Only test if docker is available
        print("Checking Docker availability...")
        docker.execute_code("print('Docker is alive')")
        print("✅ Docker is available.")
    except Exception as e:
        print(f"⚠️ Docker check failed (skipping execution test): {e}")
        # In CI environment without docker, we might want to skip or mock
    
    # 2. Initialize Agent
    agent = DataScientistAgent(name="TestODS", debate_id="test_debate_001")
    
    # 3. Test Simple Calculation Query
    query = "Calculate the sum of first 100 integers using numpy."
    print(f"\n🧪 Test Query: {query}")
    
    result = await agent.reply({"content": query})
    
    print("\n📝 Result:")
    print(result)
    
    if "5050" in str(result):
        print("✅ Calculation Test Passed!")
    else:
        print("❌ Calculation Test Failed (or mocked).")
        
    # 4. Test Plot Generation (Mock logic for now as we don't have visual)
    query_plot = "Plot a sine wave and save it."
    print(f"\n🧪 Test Plot Query: {query_plot}")
    
    # Note: This might fail if docker is not running or matplotlib not installed
    # But we just check if the agent attempts to run code
    try:
        result_plot = await agent.reply({"content": query_plot})
        print("\n📝 Plot Result:")
        print(result_plot)
    except Exception as e:
        print(f"Plot test execution error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ods_agent())
