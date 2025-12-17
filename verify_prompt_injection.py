import logging
import sys
import os

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加專案根目錄到 sys.path
sys.path.append(os.getcwd())

from api.prompt_service import PromptService
from api.database import SessionLocal

def verify_prompt_injection():
    """驗證 Base Contract 是否正確注入到 System Prompt"""
    
    logger.info("開始驗證 Prompt Injection 機制...")
    
    db = SessionLocal()
    try:
        # 1. 確保 Base Contract 已加載
        logger.info("加載 Base Contract...")
        PromptService.load_base_contract()
        
        # 2. 模擬一個測試用的 Agent Persona
        test_persona = """
你是一個測試 Agent。
你的任務是驗證系統功能。
請回答 'Hello World'。
"""
        logger.info("準備測試 Persona...")
        
        # 3. 組合 System Prompt
        logger.info("調用 compose_system_prompt...")
        full_prompt = PromptService.compose_system_prompt(
            db=db,
            override_content=test_persona
        )
        
        # 4. 驗證關鍵字 (Key Assertions)
        logger.info("驗證生成的 Prompt 內容...")
        
        checks = [
            ("System Base Contract", "系統契約標頭"),
            ("絕對規則：證據綁定", "證據綁定規則"),
            ("禁止編造具體數字", "禁止幻覺規則"),
            ("禁止引用未在工具結果中出現", "禁止引用外部來源規則"),
            ("你是一個測試 Agent", "原始 Persona 內容")
        ]
        
        all_passed = True
        
        for keyword, description in checks:
            if keyword in full_prompt:
                logger.info(f"✅ 檢測到 {description}: '{keyword}'")
            else:
                logger.error(f"❌ 未檢測到 {description}: '{keyword}'")
                all_passed = False
                
        # 5. 輸出結果摘要
        print("-" * 50)
        if all_passed:
            logger.info("✅ 驗證成功：Base Contract 已正確注入！")
            print("\n[生成的 System Prompt 預覽]:\n")
            print(full_prompt[:500] + "\n... (省略中間內容) ...\n" + full_prompt[-200:])
        else:
            logger.error("❌ 驗證失敗：Base Contract 未正確注入。")
            
    except Exception as e:
        logger.error(f"驗證過程發生例外錯誤: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    verify_prompt_injection()