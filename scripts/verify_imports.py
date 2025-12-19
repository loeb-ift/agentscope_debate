import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

print("Attempting to import worker.tasks...")
try:
    import worker.tasks
    print("✅ Successfully imported worker.tasks")
except Exception as e:
    print(f"❌ Failed to import worker.tasks: {e}")
    import traceback
    traceback.print_exc()

print("\nAttempting to import worker.debate_cycle...")
try:
    import worker.debate_cycle
    print("✅ Successfully imported worker.debate_cycle")
except Exception as e:
    print(f"❌ Failed to import worker.debate_cycle: {e}")
    import traceback
    traceback.print_exc()