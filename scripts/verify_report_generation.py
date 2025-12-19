import yaml
import json
import os
from worker.llm_utils import call_llm

def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("system_prompt", "")

def main():
    print("🚀 Starting Report Generation Verification...")
    
    # 1. Load System Prompt
    sys_prompt = load_prompt("prompts/agents/report_editor.yaml")
    if not sys_prompt:
        print("❌ Failed to load system prompt.")
        return
    
    print("✅ System Prompt Loaded.")
    
    # 2. Mock Debate Context
    mock_debate_history = """
    Topic: 2330 台積電是否值得現在買入？
    
    [Round 1]
    Pro (Growth Strategist): 台積電在先進製程 (3nm, 2nm) 擁有絕對領先優勢，AI 晶片需求強勁，NVIDIA, AMD 訂單滿載。預估 2024 EPS 可達 38 元，2025 年挑戰 45 元。給予買進評等。
    
    Con (Risk Officer): 地緣政治風險仍高，美國廠成本高昂可能拖累毛利率。且目前 PE 已接近歷史高位 (25x)，短期股價已反映利多，建議觀望。
    
    [Round 2]
    Pro (Valuation Expert): 歷史 PE 區間為 15x-28x，目前約 22x，尚未過熱。考量 AI CAGR 高達 50%，應享有更高評價。目標價上看 1200 元。
    
    Con (Industry Researcher): Intel 18A 製程可能會構成威脅，Samsung 也在積極搶單。且消費性電子復甦緩慢。
    
    [Chairman Summary]
    綜合雙方觀點，台積電技術護城河深厚，AI 長期趨勢確立，利大於弊。建議買進，但需留意地緣政治波動。目標價 1150 元。
    """
    
    user_msg = f"""
    以下是本次辯論的完整記錄，請根據這些內容，並補充必要的外部數據（假設你已經查詢到了），撰寫一份完整的投資研究報告。
    
    辯論記錄：
    {mock_debate_history}
    
    請注意：
    1. 你必須生成 [CHART_DATA] 區塊來展示預估的營收或獲利趨勢。
    2. 若辯論記錄中缺乏具體財務數據（如近三季毛利率），請在報告中標註「(模擬數據: 調用 tej.financial_summary 獲取)」並填入合理的模擬數值以展示格式。
    """
    
    # 3. Invoke LLM
    print("🤖 Invoking LLM (Report Editor)...")
    try:
        # Use sync call for simplicity in script
        content = call_llm(
            prompt=user_msg,
            system_prompt=sys_prompt,
            model="gpt-4o" # or let it fallback to config
        )
        
        print("\n" + "="*50)
        print("📄 Generated Report Output:")
        print("="*50)
        print(content)
        print("="*50)
        
        # 4. Validation
        # Allow flexible header levels (# or ###)
        checks = {
            "Structure": "1. 投資評等" in content and "9. 投資建議" in content,
            "Chart Data": "[CHART_DATA]" in content and "[/CHART_DATA]" in content,
            "Traditional Chinese": "台積電" in content and "買進" in content
        }
        
        print("\n🔍 Validation Results:")
        all_pass = True
        for k, v in checks.items():
            status = "✅ PASS" if v else "❌ FAIL"
            print(f"{k}: {status}")
            if not v: all_pass = False
            
        if all_pass:
            print("\n✨ Verification SUCCESS: Report structure and format meet requirements.")
        else:
            print("\n⚠️ Verification FAILED: Some requirements were not met.")
            
    except Exception as e:
        print(f"❌ Error during LLM invocation: {e}")

if __name__ == "__main__":
    main()