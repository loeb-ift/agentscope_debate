import os
import requests
import json
from typing import List, Dict, Any

def call_llm(prompt: str, system_prompt: str = None, model: str = None) -> str:
    """
    Call the LLM (Ollama) with the given prompt.
    """
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    if not model:
        model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

    url = f"{ollama_host}/api/chat"
    
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
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        message = result.get("message", {})
        content = message.get("content", "")
        
        # Handle tool_calls if present
        if not content and "tool_calls" in message:
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                # Convert the first tool call to the expected JSON format
                try:
                    function_call = tool_calls[0]["function"]
                    tool_name = function_call["name"]
                    function_args = function_call["arguments"]
                    
                    print(f"DEBUG: Detected tool_call - name: {tool_name}, args type: {type(function_args)}")
                    
                    # Some models might return arguments as a string, others as a dict
                    if isinstance(function_args, str):
                        # Parse JSON string
                        args_dict = json.loads(function_args)
                    else:
                        args_dict = function_args
                    
                    print(f"DEBUG: Parsed args_dict: {args_dict}")
                    
                    # Construct the JSON string our DebateCycle expects
                    # Format: {"tool": "tool_name", "params": {...}}
                    if "params" in args_dict:
                        params = args_dict["params"]
                    else:
                        # The args_dict itself contains the params
                        params = args_dict
                        
                    tool_call_json = {
                        "tool": tool_name,
                        "params": params
                    }
                    
                    result_json = json.dumps(tool_call_json, ensure_ascii=False)
                    print(f"DEBUG: Converted tool_call to JSON: {result_json}")
                    return result_json
                    
                except Exception as e:
                    print(f"ERROR: Failed to parse tool_calls: {e}")
                    print(f"DEBUG: tool_calls structure: {tool_calls}")
                    # Fall through to return empty content

        if not content:
             print(f"WARNING: LLM returned empty content. Full result: {result}")
        return content
    except Exception as e:
        print(f"Error calling LLM: {e}")
        if 'response' in locals():
             print(f"Response status: {response.status_code}")
             print(f"Response text: {response.text}")
        return f"Error: {e}"
