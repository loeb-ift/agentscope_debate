import tiktoken
import logging
from typing import Optional
from api.redis_client import get_redis_client

logger = logging.getLogger(__name__)

class PriceRegistry:
    # Prices in USD per 1M tokens
    # Default to GPT-4o pricing as a baseline for high-end models
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        # Global Pricing for GPT-5.1-chat: Input $1.25 / Cached Input $0.13 / Output $10.00
        # Assuming Cached Input logic is handled separately or averaged, using Base Input for now.
        "gpt-5.1-chat": {"input": 1.25, "output": 10.0},
        "ollama": {"input": 0.0, "output": 0.0},
        "default": {"input": 5.0, "output": 15.0} # Fallback
    }

    @staticmethod
    def get_price(model_name: str):
        # Normalize model name
        name = model_name.lower()
        if "gpt-4o" in name: return PriceRegistry.PRICING["gpt-4o"]
        if "gpt-4" in name: return PriceRegistry.PRICING["gpt-4-turbo"] # Assume turbo for generic 4
        if "gpt-3.5" in name: return PriceRegistry.PRICING["gpt-3.5-turbo"]
        if "gpt-5" in name: return PriceRegistry.PRICING["gpt-5.1-chat"]
        if "ollama" in name or "gpt-oss" in name: return PriceRegistry.PRICING["ollama"]
        
        return PriceRegistry.PRICING["default"]

class CostService:
    _encoding = None

    @classmethod
    def _get_encoding(cls):
        if cls._encoding is None:
            try:
                cls._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # Fallback if tiktoken fails (e.g. network issue downloading vocab)
                # But it usually caches.
                logger.warning("Failed to load tiktoken encoding, using rough char count fallback.")
                return None
        return cls._encoding

    @classmethod
    def calculate_tokens(cls, text: str) -> int:
        if not text: return 0
        enc = cls._get_encoding()
        if enc:
            try:
                return len(enc.encode(text))
            except Exception:
                pass
        
        # Fallback: Rough estimate (1 token ~= 4 chars)
        return len(text) // 4

    @classmethod
    async def record_usage(cls, debate_id: str, model: str, input_text: str, output_text: str):
        """
        Calculate and record usage to Redis.
        Designed to be fire-and-forget.
        """
        try:
            if not debate_id:
                return

            tokens_in = cls.calculate_tokens(input_text)
            tokens_out = cls.calculate_tokens(output_text)
            
            pricing = PriceRegistry.get_price(model)
            cost_in = (tokens_in / 1_000_000) * pricing["input"]
            cost_out = (tokens_out / 1_000_000) * pricing["output"]
            total_cost = cost_in + cost_out
            
            redis_client = get_redis_client()
            key = f"debate:{debate_id}:usage"
            
            # Atomic increments
            # Note: Redis doesn't support INCRBYFLOAT for hash fields directly in one go with pipeline in standard python lib easily without lua, 
            # but hincrbyfloat is supported.
            
            pipeline = redis_client.pipeline()
            pipeline.hincrby(key, "total_tokens", tokens_in + tokens_out)
            pipeline.hincrbyfloat(key, "total_cost", total_cost)
            
            # Record breakdown (Optional, simplified for now)
            # pipeline.hincrby(f"{key}:breakdown:{model}", "tokens", tokens_in + tokens_out)
            
            pipeline.execute()
            
            # Optional: Log for debug
            # print(f"[Cost] {model} | In: {tokens_in} Out: {tokens_out} | Cost: ${total_cost:.6f}")
            
        except Exception as e:
            print(f"⚠️ Failed to record cost: {e}")
