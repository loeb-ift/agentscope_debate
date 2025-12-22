import asyncio
from typing import List

from api.tool_registry import tool_registry
from api.config import Config
from worker.tool_invoker import call_tool


async def debug_company_sources(coid: str) -> None:
    tool_names: List[str] = []

    if Config.ENABLE_TEJ_TOOLS:
        tool_names.extend(
            [
                "tej.company_info",
                "tej.stock_price",
                "tej.financial_summary",
                "tej.financial_cover_cumulative",
            ]
        )

    tool_names.extend(
        [
            "financial.get_verified_price",
            "twse.stock_day",
            "chinatimes.stock_fundamental",
        ]
    )

    print(f"=== Company Source Debug: coid={coid} ===")
    print(f"TEJ Enabled: {Config.ENABLE_TEJ_TOOLS}")

    for name in tool_names:
        try:
            meta = tool_registry.get_tool_data(name, version="v1")
        except Exception as e:
            print(f"[{name}] registry lookup failed: {e}")
            continue

        schema = meta.get("schema") or {}
        props = schema.get("properties") or {}
        coid_field = None
        for key, spec in props.items():
            if key.lower() == "coid":
                coid_field = key
                break
        if coid_field is None and "symbol" in props:
            coid_field = "symbol"

        params = {}
        if coid_field:
            params[coid_field] = coid

        print(f"\n[{name}]")
        print(f"  schema_fields: {list(props.keys())}")
        print(f"  param_used: {params}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            result = await loop.run_in_executor(None, call_tool, name, params)
        except Exception as e:
            print(f"  call error: {e}")
            continue

        if result is None:
            print("  result: None")
            continue

        if isinstance(result, dict):
            data = result.get("data") or result.get("results")
            if not data:
                print("  result: empty data/results")
            else:
                if isinstance(data, list):
                    print(f"  result: {len(data)} records, first={data[0]}")
                else:
                    print(f"  result: non-list payload keys={list(data.keys())}")
        else:
            print(f"  result type={type(result)} value={str(result)[:200]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_company_sources.py <coid>")
        sys.exit(1)

    asyncio.run(debug_company_sources(sys.argv[1]))

