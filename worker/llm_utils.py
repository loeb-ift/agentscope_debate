import os
import requests
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENCY", "5"))
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120.0"))

# Global Semaphore
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def _process_tool_calls(tool_calls: List[Dict]) -> Optional[str]:
    """Helper to process tool calls from LLM response."""
    print(f"DEBUG: Raw tool_calls detected: {tool_calls}")
    try:
        first_tool_call = tool_calls[0]
        function_call = first_tool_call.get("function", {})
        tool_name = function_call.get("name")
        function_args = function_call.get("arguments", {})
        
        print(f"DEBUG: Processing tool_call - name: {tool_name}, args type: {type(function_args)}")
        
        if isinstance(function_args, str):
            try:
                args_dict = json.loads(function_args)
            except json.JSONDecodeError:
                try:
                    args_dict = json.loads(function_args.replace("'", '"'))
                except:
                    print(f"WARNING: Could not parse tool arguments string: {function_args}")
                    args_dict = {}
        else:
            args_dict = function_args
        
        print(f"DEBUG: Normalized args: {args_dict}")
        
        # Construct the JSON string our DebateCycle expects
        # Format: {"tool": "tool_name", "params": {...}}
        if "params" in args_dict and len(args_dict) == 1:
             params = args_dict["params"]
        else:
             params = args_dict
        
        tool_call_obj = {
            "tool": tool_name,
            "params": params
        }
        
        result_json = json.dumps(tool_call_obj, ensure_ascii=False)
        print(f"DEBUG: Converted tool_call to standardized JSON: {result_json}")
        return result_json
        
    except Exception as e:
        print(f"ERROR: Failed to process tool_calls: {e}")
        return None

def call_llm(prompt: str, system_prompt: str = None, model: str = None) -> str:
    """
    Sync Call the LLM (Ollama) with the given prompt.
    Kept for backward compatibility.
    """
    if not model:
        model = OLLAMA_MODEL

    url = f"{OLLAMA_HOST}/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        message = result.get("message", {})
        content = message.get("content", "")
        
        # Handle tool_calls if present (Ollama standard format)
        if "tool_calls" in message and message["tool_calls"]:
            tool_result = _process_tool_calls(message["tool_calls"])
            if tool_result:
                return tool_result

        if not content:
             print(f"WARNING: LLM returned empty content. Full result: {result}")
             
        return content
    except Exception as e:
        print(f"Error calling LLM (Sync): {e}")
        return f"Error: {e}"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError))
)
async def call_llm_async(prompt: str, system_prompt: str = None, model: str = None) -> str:
    """
    Async Call the LLM (Ollama) with throttling and retries.
    """
    if not model:
        model = OLLAMA_MODEL

    url = f"{OLLAMA_HOST}/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }

    async with _semaphore:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                
                # Handle tool_calls if present (Ollama standard format)
                if "tool_calls" in message and message["tool_calls"]:
                    tool_result = _process_tool_calls(message["tool_calls"])
                    if tool_result:
                        return tool_result

                if not content:
                     print(f"WARNING: LLM returned empty content. Full result: {result}")
                     
                return content
            except Exception as e:
                print(f"Error calling LLM (Async): {e}")
                raise e # Let tenacity handle retry
