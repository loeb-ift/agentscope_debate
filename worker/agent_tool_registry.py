"""
Agent Tool Registry

A minimal, framework-agnostic registry so agents can call tools by string name.
We register the TWSE global tool under a stable name: "twse.price_proof".
"""
from __future__ import annotations
from typing import Any, Callable, Dict

# Global registry mapping tool name -> callable
_TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {}


def register_tool(name: str, func: Callable[..., Any]) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("tool name must be non-empty string")
    if not callable(func):
        raise ValueError("func must be callable")
    _TOOLS_BEFORE = set(_TOOL_REGISTRY.keys())
    _TOOL_REGISTRY[name] = func


def get_tool(name: str) -> Callable[..., Any]:
    try:
        return _TOOL_REGISTRY[name]
    except KeyError:
        raise KeyError(f"tool not registered: {name}")


def call_tool(name: str, **kwargs: Any) -> Any:
    tool = get_tool(name)
    return tool(**kwargs)


# Convenience registrations
try:
    from twse_global_tool import get_twse_price_proof as _twse_price_proof
    register_tool("twse.price_proof", _twse_price_proof)
except Exception:
    pass

try:
    from price_proof_coordinator import get_price_proof as _coordinated_price_proof
    register_tool("price_proof.get", _coordinated_price_proof)
except Exception:
    pass
