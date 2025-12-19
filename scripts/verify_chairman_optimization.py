import asyncio
import json
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from worker.chairman import Chairman
from api.prompt_service import PromptService
from api.database import SessionLocal

async def test_chairman_analysis():
    # Initialize prompts
    db = SessionLocal()
    try:
        PromptService.load_defaults_from_file()
        PromptService.initialize_db_from_file(db)
    finally:
        db.close()

    chairman = Chairman(name="TestChairman")
    
    # Test cases
    topics = [
        "森鉅 (8942) 獲得產品大獎對其市場地位的影響",
        "台積電 (2330) 研發 2nm 製程的技術佈局分析",
        "某公司進行併購交易的財務影響評估"
    ]
    
    for topic in topics:
        print(f"\n{'='*50}")
        print(f"Testing Topic: {topic}")
        print(f"{'='*50}")
        
        try:
            # We mock the debate_id for logging or Redis
            result = await chairman.pre_debate_analysis(topic, debate_id="test_debate_id")
            
            print("\nAnalysis Result Structure:")
            print(json.dumps(list(result.keys()), indent=2))
            
            print("\nEntity Analysis:")
            print(json.dumps(result.get("entity_analysis"), indent=2, ensure_ascii=False))
            
            print("\nEvent Analysis:")
            print(json.dumps(result.get("event_analysis"), indent=2, ensure_ascii=False))
            
            print("\nExpected Impact:")
            print(json.dumps(result.get("expected_impact"), indent=2, ensure_ascii=False))
            
            print("\nInvestigation Factors:")
            print(json.dumps(result.get("investigation_factors"), indent=2, ensure_ascii=False))
            
            print("\nStep 5 Summary (Mapped):")
            print(result.get("step5_summary", "NOT FOUND"))
            
            print("\nStep 00 Decree (Mapped):")
            print(json.dumps(result.get("step00_decree"), indent=2, ensure_ascii=False))
            
        except Exception as e:
            print(f"Error during analysis for topic '{topic}': {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chairman_analysis())
