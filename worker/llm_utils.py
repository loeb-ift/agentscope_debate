import os
import requests
import json
import asyncio
import httpx
import time
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from api.vector_store import VectorStore
from api.config import Config

# Configuration
OLLAMA_HOST = Config.OLLAMA_HOST
OLLAMA_MODEL = Config.OLLAMA_MODEL
MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENCY", "5")) # Keep env for concurrency for now
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
        
        # Sync version doesn't support async semantic cache storage easily without a loop.
        # Skipping cache storage for sync call to avoid complexity.
        pass

        return content
    except Exception as e:
        print(f"Error calling LLM (Sync): {e}")
        return f"Error: {e}"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError))
)
async def call_llm_async(prompt: str, system_prompt: str = None, model: str = None, context_tag: str = None) -> str:
    """
    Async Call the LLM (Ollama) with throttling and retries.
    Includes Semantic Caching via Qdrant.
    
    Args:
        context_tag: Optional tag (e.g. debate_id) to scope the semantic cache.
    """
    if not model:
        model = OLLAMA_MODEL

    # --- Semantic Cache Lookup ---
    cache_query = f"System: {system_prompt}\nUser: {prompt}"
    try:
        # Construct filter if context_tag is provided
        filter_cond = None
        if context_tag:
            filter_cond = {"context": context_tag}

        # Note: Ideally we want a similarity score threshold (e.g. > 0.95).
        # VectorStore.search returns payloads of top-k matches.
        # We blindly trust the top 1 match for now as a POC.
        # Real production usage requires modifying VectorStore to return scores.
        cached_results = await VectorStore.search(
            collection_name="llm_semantic_cache",
            query=cache_query,
            limit=1,
            filter_conditions=filter_cond
        )
        
        if cached_results and len(cached_results) > 0:
             entry = cached_results[0]
             
             # Check TTL
             timestamp = entry.get('timestamp')
             ttl = getattr(Config, 'SEMANTIC_CACHE_TTL', 86400) # Default 24h
             
             is_valid = True
             if timestamp:
                 if time.time() - timestamp > ttl:
                     print(f"DEBUG: Semantic Cache Hit but EXPIRED (Age: {time.time() - timestamp:.2f}s > {ttl}s)")
                     is_valid = False
             
             if is_valid:
                 cached_resp = entry.get('response')
                 if cached_resp:
                     print("DEBUG: Semantic Cache Hit")
                     return cached_resp
                     
    except Exception as e:
        print(f"Cache lookup failed: {e}")
    # -----------------------------

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
                
                # --- Store in Semantic Cache (Async) ---
                if content:
                    try:
                        # Store prompt as text, response as metadata
                        metadata = {
                            "response": content, 
                            "model": model,
                            "timestamp": time.time()
                        }
                        if context_tag:
                            metadata["context"] = context_tag
                            
                        await VectorStore.add_texts(
                            collection_name="llm_semantic_cache",
                            texts=[cache_query],
                            metadatas=[metadata]
                        )
                    except Exception as e:
                        print(f"Failed to update cache: {e}")
                # ---------------------------------------

                return content
            except Exception as e:
                print(f"Error calling LLM (Async): {e}")
                raise e # Let tenacity handle retry
