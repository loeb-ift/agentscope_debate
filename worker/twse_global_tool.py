"""
TWSE OpenAPI Global Tool

Reference: https://openapi.twse.com.tw/#/
Core endpoint used:
- exchangeReport/STOCK_DAY?response=json&date=YYYYMMDD&stockNo=XXXX

Features:
- Fetch monthly daily prices for a given stockNo and month of `date`
- Robust parsing for ROC (民國) date returned by TWSE
- Retry, timeout, and basic error handling
- Utility to get the latest trading day's price <= asof date (非交易日自動回退)
- A proof-style response for auditability

Notes:
- stockNo should be pure numeric string for TWSE, e.g., '2480'
- date/asof use Gregorian calendar (YYYY-MM-DD)

This module is self-contained and has no external dependencies except `requests`.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import requests


TWSE_BASE = "https://openapi.twse.com.tw"
STOCK_DAY_ENDPOINT = "/api/v1/exchangeReport/STOCK_DAY"
DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_BACKOFF = 1.2
USER_AGENT = "twse-global-tool/1.0 (+https://openapi.twse.com.tw/)"


@dataclass
class PriceRow:
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class PriceProof:
    success: bool
    source: str  # 'TWSE'
    stockNo: str
    asof: dt.date
    trade_date: Optional[dt.date]
    row: Optional[PriceRow]
    request_params: Dict[str, Any]
    warnings: List[str]
    raw_count: int
    raw_months_fetched: List[str]


class TWSEClient:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, session: Optional[requests.Session] = None, verify_ssl: Optional[bool] = None):
        """
        verify_ssl: if None, read from env TWSE_VERIFY_SSL (true/false), default True.
        """
        import os
        if verify_ssl is None:
            env = os.getenv("TWSE_VERIFY_SSL", "true").lower()
            verify_ssl = (env not in ("0", "false", "no"))
        self.timeout = timeout
        self.verify_ssl = bool(verify_ssl)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        # Apply verification on session
        self.session.verify = self.verify_ssl

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Optional[BaseException] = None
        # Try OpenAPI first
        pri_url = TWSE_BASE + path
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(pri_url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:  # network or decode error
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF ** attempt)
                else:
                    break
        # Fallback to legacy rwd endpoint
        fallback_base = "https://www.twse.com.tw"
        fallback_path = "/rwd/zh/exchangeReport/STOCK_DAY"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(fallback_base + fallback_path, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF ** attempt)
                else:
                    raise
        raise RuntimeError(f"TWSE request failed: {last_exc}")

    @staticmethod
    def _gregorian_yyyymm01(date: dt.date) -> str:
        # TWSE expects Gregorian YYYYMMDD string; for month query we use YYYYMM01
        return date.strftime("%Y%m01")

    @staticmethod
    def _parse_roc_date(roc: str) -> dt.date:
        # ROC format like '112/12/02' -> 2023-12-02
        parts = roc.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid ROC date format: {roc}")
        roc_year = int(parts[0])
        year = roc_year + 1911
        month = int(parts[1])
        day = int(parts[2])
        return dt.date(year, month, day)

    def get_stock_day_month(self, stockNo: str, any_date: dt.date) -> List[PriceRow]:
        """
        Fetch monthly daily prices for stockNo for the month of `any_date`.
        Endpoint: /exchangeReport/STOCK_DAY
        Params: response=json&date=YYYYMM01&stockNo={stockNo}
        """
        if not stockNo.isdigit():
            raise ValueError("stockNo must be numeric string, e.g., '2480'")

        params = {
            "response": "json",
            "date": self._gregorian_yyyymm01(any_date),
            "stockNo": stockNo,
        }
        data = self._get(STOCK_DAY_ENDPOINT, params)
        # Expected fields: title, fields, data, ...
        rows: List[PriceRow] = []
        for item in data.get("data", []) or []:
            # According to TWSE docs:
            # [日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數]
            try:
                date = self._parse_roc_date(item[0])
                vol = int(str(item[1]).replace(",", ""))
                open_p = float(str(item[3]).replace(",", ""))
                high_p = float(str(item[4]).replace(",", ""))
                low_p = float(str(item[5]).replace(",", ""))
                close_p = float(str(item[6]).replace(",", ""))
                rows.append(PriceRow(date=date, open=open_p, high=high_p, low=low_p, close=close_p, volume=vol))
            except Exception:
                # Skip malformed rows
                continue
        return rows

    def get_latest_price_leq(self, stockNo: str, asof: dt.date) -> Optional[PriceRow]:
        """
        Return the latest trading day's price row with date <= asof.
        It fetches asof's month and the previous month to cover month boundary cases.
        """
        # this month
        rows_this = self.get_stock_day_month(stockNo, asof)
        # previous month
        first_of_month = asof.replace(day=1)
        prev_day = first_of_month - dt.timedelta(days=1)
        rows_prev = self.get_stock_day_month(stockNo, prev_day)

        rows = [r for r in (rows_this + rows_prev) if r.date <= asof]
        if not rows:
            return None
        rows.sort(key=lambda r: r.date, reverse=True)
        return rows[0]

    def get_price_proof(self, stockNo: str, asof_str: str) -> PriceProof:
        """
        High-level helper returning a proof-like structure that records parameters, warnings,
        and the chosen last trading day row.
        """
        asof = dt.datetime.strptime(asof_str, "%Y-%m-%d").date()
        warnings: List[str] = []

        # Try to fetch rows and select
        months = []
        # Pre-fetch to record months queried
        m1 = self._gregorian_yyyymm01(asof)
        pm = (asof.replace(day=1) - dt.timedelta(days=1))
        m0 = self._gregorian_yyyymm01(pm)
        months.extend([m1, m0])

        row = self.get_latest_price_leq(stockNo, asof)
        trade_date = row.date if row else None
        if row and trade_date < asof:
            warnings.append(f"Non-trading day fallback: used {trade_date.isoformat()} <= {asof.isoformat()}")

        proof = PriceProof(
            success=row is not None,
            source="TWSE",
            stockNo=stockNo,
            asof=asof,
            trade_date=trade_date,
            row=row,
            request_params={
                "endpoint": STOCK_DAY_ENDPOINT,
                "response": "json",
                "months": months,
                "stockNo": stockNo,
            },
            warnings=warnings,
            raw_count=1 if row else 0,
            raw_months_fetched=months,
        )
        return proof


# -------- Convenience CLI-like helpers (optional programmatic usage) -------- #

def _format_price_row(r: PriceRow) -> Dict[str, Any]:
    return {
        "date": r.date.isoformat(),
        "open": r.open,
        "high": r.high,
        "low": r.low,
        "close": r.close,
        "volume": r.volume,
    }


def get_twse_price_proof(symbol: str, asof: str) -> Dict[str, Any]:
    """
    Public entry for agents: normalize symbol to TWSE stockNo (numeric), then call TWSE.
    - Accepts: '2480', '2480.TW', 'TW:2480' and extracts numeric part as stockNo.
    """
    stockNo = _normalize_to_stockNo(symbol)
    client = TWSEClient()
    proof = client.get_price_proof(stockNo, asof)
    result: Dict[str, Any] = {
        "success": proof.success,
        "source": proof.source,
        "symbol_input": symbol,
        "stockNo": proof.stockNo,
        "asof": proof.asof.isoformat(),
        "trade_date": proof.trade_date.isoformat() if proof.trade_date else None,
        "row": _format_price_row(proof.row) if proof.row else None,
        "request_params": proof.request_params,
        "warnings": proof.warnings,
        "raw_months_fetched": proof.raw_months_fetched,
    }
    return result


def _normalize_to_stockNo(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.endswith(".TW"):
        s = s.split(".")[0]
    if ":" in s:
        s = s.split(":", 1)[1]
    # keep only digits
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        raise ValueError(f"Cannot extract numeric stockNo from symbol: {symbol}")
    return digits


# Minimal manual test (not executed automatically)
if __name__ == "__main__":
    # Example: python twse_global_tool.py
    symbol = "2480.TW"
    asof = "2025-12-13"
    out = get_twse_price_proof(symbol, asof)
    print(json.dumps(out, ensure_ascii=False, indent=2))
