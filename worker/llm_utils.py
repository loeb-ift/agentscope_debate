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
        
        # Handle tool_calls if present (Ollama standard format)
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = message.get("tool_calls", [])
            print(f"DEBUG: Raw tool_calls detected: {tool_calls}")
            
            try:
                # We currently only handle the first tool call
                first_tool_call = tool_calls[0]
                function_call = first_tool_call.get("function", {})
                tool_name = function_call.get("name")
                function_args = function_call.get("arguments", {})
                
                print(f"DEBUG: Processing tool_call - name: {tool_name}, args type: {type(function_args)}")
                
                # Normalize arguments to dict
                if isinstance(function_args, str):
                    try:
                        args_dict = json.loads(function_args)
                    except json.JSONDecodeError:
                         # Try to fix common JSON errors (like single quotes)
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
                
                # Check if params are nested or flat (flat is preferred/standard for function calling)
                # If the model put everything under "params" key, extract it.
                if "params" in args_dict and len(args_dict) == 1:
                     params = args_dict["params"]
                else:
                     params = args_dict
                
                tool_call_obj = {
                    "tool": tool_name,
                    "params": params
                }
                
                # Return this AS the content, so DebateCycle sees it as a JSON response
                result_json = json.dumps(tool_call_obj, ensure_ascii=False)
                print(f"DEBUG: Converted tool_call to standardized JSON: {result_json}")
                return result_json
                
            except Exception as e:
                print(f"ERROR: Failed to process tool_calls: {e}")
                # Fallback to content if tool processing fails

        if not content:
             print(f"WARNING: LLM returned empty content and no valid tool_calls. Full result: {result}")
             
        return content
    except Exception as e:
        print(f"Error calling LLM: {e}")
        if 'response' in locals():
             print(f"Response status: {response.status_code}")
             print(f"Response text: {response.text}")
        return f"Error: {e}"
