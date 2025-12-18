import os
import requests
import json
import asyncio
import httpx
import time
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
from api.vector_store import VectorStore
from api.config import Config
from api.cost_utils import CostService

# Configuration Constants
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120.0"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENCY", "5"))

# Global Semaphore
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

class LLMProvider:
    def __init__(self):
        pass

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        raise NotImplementedError

    def chat_completion_sync(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        raise NotImplementedError

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.host = getattr(Config, "OLLAMA_HOST", "http://localhost:11434")
        if not self.host:
             self.host = "http://localhost:11434"
             
        if not self.host.startswith(("http://", "https://")):
            self.host = f"http://{self.host}"
        
        self.host = self.host.rstrip("/")
        
        # Check for container environment
        if self.host and ("0.0.0.0" in self.host or "localhost" in self.host or "127.0.0.1" in self.host):
             # Just a warning, not blocking
             pass

    def _prepare_payload(self, messages: List[Dict], tools: List[Dict] = None, model: str = None):
        payload = {
            "model": model or Config.OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools
        return payload

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = f"{self.host}/api/chat"
        payload = self._prepare_payload(messages, tools, model)
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return self._parse_response(result)

    def chat_completion_sync(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = f"{self.host}/api/chat"
        payload = self._prepare_payload(messages, tools, model)
        
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return self._parse_response(result)

    def _parse_response(self, result: Dict) -> str:
        message = result.get("message", {})
        content = message.get("content", "")
        
        if "tool_calls" in message and message["tool_calls"]:
            tool_result = _process_tool_calls(message["tool_calls"])
            if tool_result:
                return tool_result
        return content

class AzureOpenAIProvider(LLMProvider):
    def __init__(self):
        self.endpoint = Config.AZURE_OPENAI_ENDPOINT
        self.api_key = Config.AZURE_OPENAI_API_KEY
        self.deployment = Config.AZURE_OPENAI_MODEL_DEPLOYMENT
        self.api_version = getattr(Config, "AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        # Validate config
        if not self.endpoint or not self.api_key or not self.deployment:
            print("⚠️ Azure OpenAI Config Missing. Please check .env")

    def _get_url(self):
        # Format: https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version={version}
        base = self.endpoint.rstrip('/')
        return f"{base}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"

    def _prepare_payload(self, messages: List[Dict], tools: List[Dict] = None, model: str = None):
        # Azure OpenAI expects standard OpenAI chat format
        # Model is handled via deployment URL, but some libs pass it in body. We can skip it or pass deployment name.
        payload = {
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, model)
        headers = self._get_headers()
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return self._parse_response(result)

    def chat_completion_sync(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, model)
        headers = self._get_headers()
        
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return self._parse_response(result)

    def _parse_response(self, result: Dict) -> str:
        # Standard OpenAI response format
        choices = result.get("choices", [])
        if not choices:
            return ""
            
        message = choices[0].get("message", {})
        content = message.get("content") or "" # Content can be None if tool_calls present
        
        if "tool_calls" in message and message["tool_calls"]:
            tool_result = _process_tool_calls(message["tool_calls"])
            if tool_result:
                return tool_result
        return content

class OpenAIProvider(LLMProvider):
    # Implementation for generic OpenAI compatible APIs (DeepSeek, etc.)
    def __init__(self):
        self.base_url = getattr(Config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = getattr(Config, "OPENAI_API_KEY", "")
        self.model = getattr(Config, "OPENAI_MODEL", "gpt-4")

    def _get_url(self):
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _prepare_payload(self, messages: List[Dict], tools: List[Dict] = None, model: str = None):
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def chat_completion(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, model)
        headers = self._get_headers()
        
        # Debug Log
        safe_headers = headers.copy()
        if "api-key" in safe_headers:
            safe_headers["api-key"] = "***"
        print(f"DEBUG: Azure Request URL: {url}")
        print(f"DEBUG: Azure Headers: {safe_headers}")
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return self._parse_response(result)

    def chat_completion_sync(self, messages: List[Dict], tools: List[Dict] = None, model: str = None) -> str:
        url = self._get_url()
        payload = self._prepare_payload(messages, tools, model)
        headers = self._get_headers()
        
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return self._parse_response(result)

    def _parse_response(self, result: Dict) -> str:
        # Same as Azure
        choices = result.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content") or ""
        if "tool_calls" in message and message["tool_calls"]:
            tool_result = _process_tool_calls(message["tool_calls"])
            if tool_result:
                return tool_result
        return content

def get_llm_provider() -> LLMProvider:
    provider_name = getattr(Config, "LLM_PROVIDER", "ollama").lower()
    
    if provider_name == "azure_openai":
        return AzureOpenAIProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    else:
        return OllamaProvider()

# --- Common Utils ---

def _process_tool_calls(tool_calls: List[Dict]) -> Optional[str]:
    """Helper to process tool calls from LLM response."""
    print(f"DEBUG: Raw tool_calls detected: {tool_calls}")
    try:
        first_tool_call = tool_calls[0]
        function_call = first_tool_call.get("function", {})
        tool_name = function_call.get("name")
        function_args = function_call.get("arguments", {})
        
        # print(f"DEBUG: Processing tool_call - name: {tool_name}, args type: {type(function_args)}")
        
        if isinstance(function_args, str):
            try:
                args_dict = json.loads(function_args)
            except json.JSONDecodeError:
                try:
                    # Fix single quotes
                    args_dict = json.loads(function_args.replace("'", '"'))
                except:
                    print(f"WARNING: Could not parse tool arguments string: {function_args}")
                    args_dict = {}
        else:
            args_dict = function_args
        
        # Standardize params
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

# --- Main Interfaces ---

def call_llm(prompt: str, system_prompt: str = None, model: str = None, tools: List[Dict] = None) -> str:
    """Sync Call Wrapper"""
    provider = get_llm_provider()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        start_time = time.time()
        print(f"DEBUG: Calling LLM (Sync) via {type(provider).__name__}...")
        content = provider.chat_completion_sync(messages, tools, model)
        elapsed = time.time() - start_time
        print(f"DEBUG: LLM (Sync) finished in {elapsed:.2f}s")
        return content
    except Exception as e:
        print(f"Error calling LLM (Sync): {e}")
        # Log payload debug if bad request
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 400:
             print(f"CRITICAL: 400 Bad Request. Body: {e.response.text}")
        return f"Error: {e}"

# --- Semantic Cache ---

class SemanticCacheBuffer:
    _instance = None
    def __init__(self):
        self._buffer = []
        self.batch_size = 5
        self.stats = {"hits": 0, "misses": 0}
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SemanticCacheBuffer()
        return cls._instance
        
    async def add(self, query: str, metadata: Dict[str, Any]):
        self._buffer.append((query, metadata))
        if len(self._buffer) >= self.batch_size:
            await self.flush()
            
    async def flush(self):
        if not self._buffer: return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            await VectorStore.add_texts(
                collection_name="llm_semantic_cache",
                texts=[b[0] for b in batch],
                metadatas=[b[1] for b in batch]
            )
        except Exception as e:
            print(f"Failed to flush semantic cache: {e}")

_semantic_cache_buffer = SemanticCacheBuffer.get_instance()

async def _update_semantic_cache(cache_query: str, content: str, model: str, context_tag: Optional[str]):
    try:
        metadata = {
            "response": content,
            "model": model or Config.OLLAMA_MODEL,
            "timestamp": time.time()
        }
        if context_tag: metadata["context"] = context_tag
        await _semantic_cache_buffer.add(cache_query, metadata)
    except Exception as e:
        print(f"Failed to queue cache update: {e}")

async def _call_llm_async_impl(prompt: str, system_prompt: str = None, model: str = None, tools: List[Dict] = None, debate_id: str = None) -> str:
    """Internal Async Implementation"""
    provider = get_llm_provider()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    # Extract input text for cost calc
    input_text = json.dumps(messages, ensure_ascii=False)

    async with _semaphore:
        try:
            start_time = time.time()
            print(f"DEBUG: Calling LLM (Async) via {type(provider).__name__}...")
            content = await provider.chat_completion(messages, tools, model)
            elapsed = time.time() - start_time
            print(f"DEBUG: LLM (Async) finished in {elapsed:.2f}s")
            
            # --- Cost Recording ---
            if debate_id:
                asyncio.create_task(CostService.record_usage(
                    debate_id=debate_id,
                    model=model or Config.LLM_PROVIDER, # Use provider name as model proxy if model not passed
                    input_text=input_text,
                    output_text=content
                ))
            # ---------------------
            
            return content
        except Exception as e:
             if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 400:
                 print(f"CRITICAL: 400 Bad Request. Body: {e.response.text}")
             print(f"Error calling LLM (Async): {e}")
             raise e

async def call_llm_async(prompt: str, system_prompt: str = None, model: str = None, context_tag: str = None, tools: List[Dict] = None) -> str:
    """Async Wrapper with Semantic Caching & Retry"""
    
    # Extract debate_id from context_tag (Format: "debate_id:agent_name:...")
    debate_id = None
    if context_tag and ":" in context_tag:
        debate_id = context_tag.split(":")[0]

    # Semantic Cache Logic
    cache_query = f"System: {system_prompt}\nUser: {prompt}"
    skip_cache = False
    
    time_keywords = ["今天", "現在", "current", "today", "now", "real-time"]
    has_time_keyword = any(k in prompt.lower() for k in time_keywords)
    
    if has_time_keyword and not tools:
         skip_cache = True
    
    if not skip_cache:
        try:
            filter_cond = {"context": context_tag} if context_tag else None
            cached_results = await VectorStore.search(
                collection_name="llm_semantic_cache",
                query=cache_query,
                limit=1,
                filter_conditions=filter_cond
            )
            
            if cached_results:
                 entry = cached_results[0]
                 timestamp = entry.get('timestamp')
                 ttl = getattr(Config, 'SEMANTIC_CACHE_TTL', 86400)
                 
                 is_valid = True
                 if timestamp and (time.time() - timestamp > ttl):
                     is_valid = False
                 
                 if is_valid:
                     cached_resp = entry.get('response')
                     if cached_resp:
                         if has_time_keyword and "{" not in cached_resp:
                             pass # Skip volatile text
                         elif '"tool": "reset_equipped_tools"' in cached_resp:
                             pass # Skip unsafe meta-tool
                         else:
                             print("DEBUG: Semantic Cache Hit")
                             _semantic_cache_buffer.stats["hits"] += 1
                             return cached_resp
        except Exception as e:
            print(f"Cache lookup failed: {e}")

    _semantic_cache_buffer.stats["misses"] += 1

    try:
        content = await _call_llm_async_impl(prompt, system_prompt, model, tools=tools, debate_id=debate_id)
        if content:
            asyncio.create_task(_update_semantic_cache(cache_query, content, model, context_tag))
        return content

    except RetryError:
        error_msg = f"LLM Generation Failed: Timeout after multiple retries. Provider: {Config.LLM_PROVIDER}"
        print(f"CRITICAL ERROR: {error_msg}")
        return f"Error: {error_msg}"
    except Exception as e:
        return f"Error: {e}"
