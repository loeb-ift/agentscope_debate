from typing import Any, Tuple

SOURCE_STM = "STM"
SOURCE_L1 = "L1"
SOURCE_L2 = "L2"
SOURCE_LTM = "LTM"
SOURCE_TOOL = "TOOL"


def decide_source(query: dict, ctx: Any) -> Tuple[str, Any]:
    """
    Question-first decision flow skeleton:
    1) STM -> 2) L1 -> 3) L2 -> 4) LTM -> 5) TOOL
    Returns: (source_tag, payload)
    """
    # 1) STM
    hit = getattr(ctx, "stm", {}).get(query.get("key")) if hasattr(ctx, "stm") else None
    if hit is not None:
        return SOURCE_STM, hit

    # 2) L1 (in-process cache)
    l1 = getattr(ctx, "l1", {}).get(query.get("key")) if hasattr(ctx, "l1") else None
    if l1 is not None:
        return SOURCE_L1, l1

    # 3) L2 (shared cache)
    l2 = getattr(ctx, "l2", {}).get(query.get("key")) if hasattr(ctx, "l2") else None
    if l2 is not None:
        return SOURCE_L2, l2

    # 4) LTM (artifact store retrieval)
    if hasattr(ctx, "ltm_search"):
        hits = ctx.ltm_search(query)
        if hits:
            return SOURCE_LTM, hits[0]

    # 5) TOOL (external)
    if hasattr(ctx, "invoke_tool"):
        res = ctx.invoke_tool(query)
        return SOURCE_TOOL, res

    return SOURCE_TOOL, None
