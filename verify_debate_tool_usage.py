import sys
import json
import os
import logging
from typing import Dict, Any, List

# Add current directory to path so we can import modules
sys.path.append(os.getcwd())

from worker.llm_utils import call_llm
from api.tool_registry import tool_registry
from worker.dynamic_tool_loader import DynamicToolLoader, OpenAPIToolAdapter

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DebateToolVerifier")

def ensure_chinatimes_tool():
    """
    確保 ChinaTimes 工具已註冊。
    如果 DynamicToolLoader 沒載入 (可能沒在 DB)，則手動註冊一個用於測試。
    """
    tool_name = "news.search_chinatimes"
    
    # 嘗試從 DB 載入所有工具
    logger.info("嘗試載入動態工具...")
    try:
        DynamicToolLoader.load_all_tools(tool_registry)
    except Exception as e:
        logger.warning(f"DynamicToolLoader 載入失敗 (可能 DB 未連線): {e}")

    # 檢查是否已存在
    tools = tool_registry.list_tools()
    # tool_registry keys are "name:version"
    found = any(k.startswith(tool_name) for k in tools.keys())
    
    if found:
        logger.info(f"✅ 工具 {tool_name} 已存在於 Registry。")
        return

    logger.info(f"⚠️ 工具 {tool_name} 未找到，正在進行手動註冊用於測試...")
    
    # 定義 ChinaTimes 的 OpenAPI Spec (基於 verify_chinatimes_tool.py 的發現)
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {
            "/search/content": {
                "get": {
                    "summary": "搜尋中時新聞網",
                    "description": "根據關鍵字搜尋相關新聞",
                    "operationId": "search_news",
                    "parameters": [
                        {
                            "name": "Keyword",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "搜尋關鍵字 (例如: 公司名稱, 議題)"
                        }
                    ]
                }
            }
        }
    }

    # 建立 Adapter
    adapter = OpenAPIToolAdapter({
        'name': tool_name,
        'version': 'v1',
        'description': '搜尋中時新聞網 (ChinaTimes) 的最新新聞報導',
        'openapi_spec': openapi_spec,
        'base_url': 'https://es.chinatimes.com',
        'auth_type': 'none',
        'provider': 'chinatimes',
        'timeout': 15
    })

    # 註冊
    tool_registry.register(adapter, group="news")
    logger.info(f"✅ {tool_name} 手動註冊完成。")

def convert_registry_to_ollama_tools(tool_names: List[str]) -> List[Dict]:
    """將 Registry 中的工具轉換為 Ollama Tool 格式"""
    ollama_tools = []
    
    for name in tool_names:
        try:
            tool_data = tool_registry.get_tool_data(name)
            schema = tool_data["schema"]
            description = tool_data["description"]
            
            # 如果 description 是字典 (來自 .describe() 的回傳)，提取其中的描述字串
            if isinstance(description, dict):
                description = description.get("description", "")
            
            # 轉換 JSON Schema 到 Ollama Function 格式
            function_def = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": schema
                }
            }
            ollama_tools.append(function_def)
        except Exception as e:
            logger.error(f"轉換工具 {name} 失敗: {e}")
            
    return ollama_tools

def run_simulation():
    """執行辯論場景模擬"""
    
    # 1. 環境設置
    ensure_chinatimes_tool()
    
    target_tool = "news.search_chinatimes"
    topic = "分析中光電的近期市場動態"
    
    system_prompt = (
        "你是產業分析師，正在參與一場關於市場動態的辯論。\n"
        "你的目標是使用新聞工具查找事實來支持你的論點。\n"
        "請根據用戶的要求，決定是否調用工具。如果需要調用工具，請直接調用。"
    )
    
    user_prompt = f"Topic: {topic}\n請查找關於'中光電'的最新新聞，並說明其擴廠計畫或重要動態。"
    
    logger.info("="*50)
    logger.info("🚀 開始模擬 Agent 工具調用場景")
    logger.info(f"System Prompt: {system_prompt}")
    logger.info(f"User Prompt: {user_prompt}")
    logger.info("="*50)

    # 準備工具定義
    tools_payload = convert_registry_to_ollama_tools([target_tool])
    logger.info(f"已準備工具定義: {[t['function']['name'] for t in tools_payload]}")

    # 2. 第一次調用 LLM (思考與工具調用)
    logger.info("🤖 步驟 1: 調用 LLM (預期產出 Tool Call)...")
    try:
        response_1 = call_llm(
            prompt=user_prompt,
            system_prompt=system_prompt,
            tools=tools_payload
        )
    except Exception as e:
        logger.error(f"LLM 調用失敗: {e}")
        return

    logger.info(f"LLM 回應 (Raw): {response_1}")

    # 3. 解析與執行工具
    tool_call_json = None
    try:
        # call_llm 會回傳 JSON string: {"tool": "name", "params": {...}}
        if response_1.strip().startswith("{"):
            tool_call_json = json.loads(response_1)
        else:
            logger.warning("❌ LLM 沒有回傳 JSON 格式的 Tool Call，而是回傳了純文本。")
            print(f"Content: {response_1}")
            return
            
    except json.JSONDecodeError:
        logger.error("❌ 無法解析 LLM 回傳的 JSON")
        return

    if tool_call_json and "tool" in tool_call_json:
        tool_name = tool_call_json["tool"]
        tool_params = tool_call_json.get("params", {})
        
        logger.info(f"🎯 檢測到 Tool Call: {tool_name}")
        logger.info(f"參數: {tool_params}")
        
        # 驗證是否為預期工具
        if tool_name != target_tool:
            logger.warning(f"❌ LLM 調用了非預期工具: {tool_name}")
            return

        # 執行工具
        logger.info("⚙️ 步驟 2: 執行工具...")
        try:
            tool_instance = tool_registry.get_tool_data(tool_name)["instance"]
            tool_result = tool_instance.invoke(**tool_params)
            
            # 簡化顯示結果 (避免過長)
            result_str = json.dumps(tool_result, ensure_ascii=False)
            preview_len = 500
            result_preview = result_str[:preview_len] + "..." if len(result_str) > preview_len else result_str
            
            logger.info(f"✅ 工具執行成功。結果預覽: {result_preview}")
            
        except Exception as e:
            logger.error(f"❌ 工具執行失敗: {e}")
            tool_result = {"error": str(e)}

        # 4. 第二次調用 LLM (總結回答)
        logger.info("🤖 步驟 3: 回傳結果給 LLM 進行總結...")
        
        # 建構新的 Prompt，包含工具結果
        follow_up_prompt = (
            f"User Question: {user_prompt}\n\n"
            f"Tool '{tool_name}' execution result: {json.dumps(tool_result, ensure_ascii=False)}\n\n"
            "請根據上述工具執行的結果，回答用戶的問題。請引用具體的新聞標題或內容。"
        )
        
        response_2 = call_llm(
            prompt=follow_up_prompt,
            system_prompt=system_prompt,
            # 第二次調用通常不需要再傳工具，除非是 Multi-turn agent
            # 這裡我們只傳 tools=[] 或 None
            tools=None 
        )
        
        logger.info("="*50)
        logger.info("📝 LLM 最終回答:")
        print(response_2)
        logger.info("="*50)
        
    else:
        logger.warning("❌ 未檢測到有效的 Tool Call 結構")

if __name__ == "__main__":
    run_simulation()