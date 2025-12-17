"""
TEJClient adapter that conforms to price_proof_coordinator.TEJLike interface.
It calls TEJ Datatables TRAIL/TAPRCD (unadjusted daily prices) and maps to
standard rows: {tdate, open, high, low, close, volume}.

Environment variables:
- TEJ_API_KEY: your TEJ API key
- TEJ_BASE_URL: optional, default https://api.tej.com.tw/api/datatables

Usage:
    from adapters_integration.tej_price_client import TEJClient
    tej = TEJClient()
    rows, meta = tej.call_stock_price('2330', '2025-11-01', '2025-12-13', 500, 0)
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_BASE = "https://api.tej.com.tw/api/datatables"
USER_AGENT = "agentscope-tej-price-client/1.0"
TIMEOUT = 15
MAX_RETRIES = 3
BACKOFF = 1.3


class TEJClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = TIMEOUT):
        self.base_url = (base_url or os.getenv("TEJ_BASE_URL") or DEFAULT_BASE).rstrip('/')
        self.api_key = api_key or os.getenv("TEJ_API_KEY")
        if not self.api_key:
            raise RuntimeError("TEJ_API_KEY is not set. Provide via env or constructor.")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        })

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Optional[BaseException] = None
        q = dict(params)
        q["api_key"] = self.api_key
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(url, params=q, timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF ** attempt)
                else:
                    raise
        raise RuntimeError(f"TEJ request failed: {last_exc}")

    def call_stock_price(
        self,
        coid: str,
        date_gte: Optional[str],
        date_lte: Optional[str],
        limit: int = 500,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Query TRAIL/TAPRCD with filters coid, mdate.gte, mdate.lte.
        Map TEJ columns to standard keys: tdate, open, high, low, close, volume.
        """
        path = "TRAIL/TAPRCD.json"
        params: Dict[str, Any] = {}
        if coid:
            params["coid"] = coid
        if date_gte:
            params["mdate.gte"] = date_gte
        if date_lte:
            params["mdate.lte"] = date_lte
        if limit is not None:
            params["opts.limit"] = int(limit)
        if offset:
            params["opts.offset"] = int(offset)

        data = self._get(path, params)
        rows = data.get("data") or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            # TEJ TAPRCD typical columns: mdate, open_d, high_d, low_d, close_d, volume
            try:
                mapped = {
                    "tdate": r.get("mdate"),
                    "open": _to_float(r.get("open_d")),
                    "high": _to_float(r.get("high_d")),
                    "low": _to_float(r.get("low_d")),
                    "close": _to_float(r.get("close_d")),
                    "volume": int(float(r.get("volume") or 0)),
                }
                # Filter out malformed
                if mapped["tdate"]:
                    out.append(mapped)
            except Exception:
                continue
        meta = {k: v for k, v in data.items() if k != "data"}
        return out, meta


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)
    except Exception:
        s = str(x).replace(",", "").strip()
        try:
            return float(s)
        except Exception:
            return 0.0
