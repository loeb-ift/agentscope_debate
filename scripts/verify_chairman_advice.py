import asyncio
import logging
from unittest.mock import MagicMock, patch
from worker.chairman import Chairman

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_chairman_advice():
    # Mocking dependencies
    debate_id = "test_debate_id"
    topic = "Should I invest in TSMC?"
    verdict = "Yes, due to strong fundamentals and market dominance."
    
    # Initialize Chairman
    chairman = Chairman("Chairman")
    
    # Mock call_llm_async to return simulated responses
    async def mock_call_llm_async(prompt, **kwargs):
        if "AdvicePlan" in kwargs.get("context_tag", ""):
            return "What is the latest dividend yield of TSMC?\nHow to download TSMC's latest financial report?\nWhat are the major risks for the semiconductor industry in 2024?"
        elif "FinalAdvice" in kwargs.get("context_tag", ""):
            return "## Actionable Advice\n1. Download the latest financial report from the TSMC website.\n2. Monitor the dividend yield quarterly.\n3. Keep an eye on geopolitical risks."
        return "Generic LLM Response"

    # Mock call_tool to return simulated tool results
    def mock_call_tool(tool_name, params):
        logger.info(f"Tool called: {tool_name} with params: {params}")
        if tool_name == "searxng.search":
            return [{"title": "TSMC Dividend", "snippet": "TSMC dividend yield is around 2%."}]
        return {}

    # Patch dependencies
    with patch("worker.chairman.call_llm_async", side_effect=mock_call_llm_async), \
         patch("worker.tool_invoker.call_tool", side_effect=mock_call_tool), \
         patch("worker.chairman.get_redis_client"), \
         patch("worker.chairman.SessionLocal"):
         
         # Test _conduct_extended_research
        logger.info("Testing _conduct_extended_research...")
        research_results = await chairman._conduct_extended_research(topic, verdict, debate_id)
        logger.info(f"Research Results:\n{research_results}")
        assert "TSMC Dividend" in research_results
        
        logger.info("Test passed!")

if __name__ == "__main__":
    asyncio.run(test_chairman_advice())