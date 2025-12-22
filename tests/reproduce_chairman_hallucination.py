import sys
import os
import asyncio
import json

# Setup environment to run from project root
sys.path.append(os.getcwd())

# Mock environment variables if needed
os.environ["DEBUG_LOG_ENABLE"] = "true"

from worker.chairman import Chairman
from api.database import SessionLocal

async def reproduce():
    print("Initializing Chairman...")
    chairman = Chairman("Chairman")
    
    topic = "關於敦陽科技(2480)的未來展望"
    debate_id = "test_debug_2480"
    
    print(f"Starting Pre-Debate Analysis for: {topic}")
    
    try:
        # Run pre-debate analysis
        result = await chairman.pre_debate_analysis(topic, debate_id=debate_id)
        
        print("\n" + "="*50)
        print("ANALYSIS RESULT")
        print("="*50)
        
        analysis = result.get("analysis", {})
        bg_info = result.get("bg_info", "")
        
        print(f"Background Info Length: {len(bg_info)}")
        print(f"Background Info Preview: {bg_info[:500]}...")
        
        step5_summary = analysis.get("step5_summary", "")
        print("\nStep 5 Summary (Strategic Analysis):")
        if isinstance(step5_summary, dict):
            print(json.dumps(step5_summary, ensure_ascii=False, indent=2))
        else:
            print(step5_summary)
            
        # Check for specific hallucinations
        print("\n" + "="*50)
        print("HALLUCINATION CHECK")
        print("="*50)
        
        hallucination_indicators = [
            "半導體需求疲軟", 
            "美元走強", 
            "毛利率縮水",
            "消費性電子"
        ]
        
        found_hallucinations = []
        summary_str = str(step5_summary)
        for indicator in hallucination_indicators:
            if indicator in summary_str:
                found_hallucinations.append(indicator)
                
        if found_hallucinations:
            print(f"⚠️ POTENTIAL HALLUCINATIONS FOUND: {found_hallucinations}")
            print("The Chairman might be bluffing with generic macro reasons.")
        else:
            print("✅ No obvious generic hallucinations found in summary.")

        # Check for actual data
        data_indicators = ["2480", "敦陽", "資訊服務", "系統整合"]
        found_data = []
        for indicator in data_indicators:
            if indicator in summary_str:
                found_data.append(indicator)
        
        print(f"ℹ️ DATA MATCHES: {found_data}")

    except Exception as e:
        print(f"Error during reproduction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reproduce())
