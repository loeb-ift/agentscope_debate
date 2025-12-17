"""
Multi-source Price Proof Coordinator

Unifies access to price proof with source preference:
- TEJ (preferred, if client provided)
- TWSE (fallback using public OpenAPI)
- Yahoo (secondary fallback; best-effort)

Provides a single entry: get_price_proof(symbol: str, asof: str, tej_client: Optional[TEJLike]) -> Dict

Notes:
- symbol can be '2480', '2480.TW', 'TW:2480'
- asof is 'YYYY-MM-DD'
- TEJ client is optional; pass an adapter implementing call_stock_price()
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

# Optional dependency for Yahoo
try:
    import yfinance as yf  # type: ignore
    _YF_AVAILABLE = True
except Exception:
    yf = None
    _YF_AVAILABLE = False

from twse_global_tool import TWSEClient, PriceRow as TWSEPriceRow
from adapters_integration.tej_price_client import TEJClient as DefaultTEJClient


# ----------------- Data models -----------------

@dataclass
class PriceRow:
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: int


def _row_to_dict(r: PriceRow) -> Dict[str, Any]:
    return {
        "date": r.date.isoformat(),
        "open": r.open,
        "high": r.high,
        "low": r.low,
        "close": r.close,
        "volume": r.volume,
    }


# ----------------- Symbol normalization -----------------

def normalize_symbol(symbol: str) -> Dict[str, str]:
    s = symbol.strip().upper()
    yahoo = s
    if s.endswith('.TW'):
        base = s.split('.')[0]
        return {'coid': base, 'yahoo_ticker': s, 'market': 'TW'}
    if ':' in s:
        prefix, code = s.split(':', 1)
        if prefix in ('TW', 'TSE'):
            return {'coid': code, 'yahoo_ticker': f'{code}.TW', 'market': 'TW'}
        yahoo = code
    # digits only -> assume TW
    if s.isdigit() and 3 <= len(s) <= 6:
        return {'coid': s, 'yahoo_ticker': f'{s}.TW', 'market': 'TW'}
    # fallback
    digits = ''.join(c for c in s if c.isdigit()) or s
    return {'coid': digits, 'yahoo_ticker': yahoo, 'market': 'TW'}


# ----------------- TEJ interface (injected) -----------------

class TEJLike:
    """Protocol-like interface expected from a TEJ adapter.
    Must implement call_stock_price(coid, date_gte, date_lte, limit, offset) -> (rows, meta)
    rows should contain fields: tdate, open, high, low, close, volume
    """
    def call_stock_price(self, coid: str, date_gte: Optional[str], date_lte: Optional[str],
                         limit: int = 500, offset: int = 0):
        raise NotImplementedError


def _parse_tej_row(row: Dict[str, Any]) -> PriceRow:
    d = dt.datetime.strptime(str(row['tdate']), '%Y-%m-%d').date()
    return PriceRow(
        date=d,
        open=float(row['open']),
        high=float(row['high']),
        low=float(row['low']),
        close=float(row['close']),
        volume=int(row.get('volume') or 0)
    )


def _select_latest_leq(rows: List[Dict[str, Any]], asof: dt.date) -> Optional[PriceRow]:
    candidates: List[Tuple[dt.date, Dict[str, Any]]] = []
    for r in rows:
        rd = dt.datetime.strptime(str(r['tdate']), '%Y-%m-%d').date()
        if rd <= asof:
            candidates.append((rd, r))
    if not candidates:
        return None
    rd, r = sorted(candidates, key=lambda x: x[0], reverse=True)[0]
    return _parse_tej_row(r)


# ----------------- Yahoo helper -----------------

def _select_yahoo_latest_leq(yahoo_ticker: str, asof: dt.date) -> Optional[PriceRow]:
    if not _YF_AVAILABLE:
        return None
    start = asof - dt.timedelta(days=30)
    end = asof + dt.timedelta(days=1)
    df = yf.download(yahoo_ticker, start=start, end=end, interval='1d', auto_adjust=False, progress=False)
    if df is None or df.empty:
        return None
    df = df[df.index.date <= asof]
    if df.empty:
        return None
    last = df.iloc[-1]
    def _to_float(x):
        try:
            # pandas Series scalar
            if hasattr(x, 'item'):
                return float(x.item())
            return float(x)
        except Exception:
            # as a last resort
            return float(x.values[0]) if hasattr(x, 'values') else float(x)
    return PriceRow(
        date=df.index[-1].date(),
        open=_to_float(last['Open']),
        high=_to_float(last['High']),
        low=_to_float(last['Low']),
        close=_to_float(last['Close']),
        volume=int(_to_float(last.get('Volume') or 0))
    )


# ----------------- Coordinator -----------------

def get_price_proof(symbol: str, asof: str, tej_client: Optional[TEJLike] = None,
                    tolerance_close_pct: float = 0.005) -> Dict[str, Any]:
    """
    Unified entry to get a price proof using multiple sources with preference.
    Returns a dictionary ready for agent consumption.
    """
    norm = normalize_symbol(symbol)
    asof_date = dt.datetime.strptime(asof, '%Y-%m-%d').date()

    warnings: List[str] = []
    cross: Dict[str, Any] = {}

    # 1) TEJ preferred
    if tej_client is not None:
        params = {
            'coid': norm['coid'],
            'tdate.gte': (asof_date - dt.timedelta(days=30)).strftime('%Y-%m-%d'),
            'tdate.lte': asof,
            'opts.limit': 500,
            'opts.offset': 0,
        }
        try:
            rows, _meta = tej_client.call_stock_price(
                coid=norm['coid'],
                date_gte=params['tdate.gte'],
                date_lte=params['tdate.lte'],
                limit=params['opts.limit'],
                offset=params['opts.offset'],
            )
            chosen = _select_latest_leq(rows or [], asof_date)
            if chosen:
                # cross-check
                twse = None
                try:
                    twse_client = TWSEClient()
                    twse_row = twse_client.get_latest_price_leq(norm['coid'], chosen.date)
                    if twse_row:
                        twse = PriceRow(date=twse_row.date, open=twse_row.open, high=twse_row.high,
                                        low=twse_row.low, close=twse_row.close, volume=twse_row.volume)
                except Exception as e:
                    warnings.append(f'TWSE cross-check warning: {e!r}')

                yahoo = None
                try:
                    yahoo = _select_yahoo_latest_leq(norm['yahoo_ticker'], chosen.date)
                except Exception as e:
                    warnings.append(f'Yahoo cross-check warning: {e!r}')

                if twse:
                    cross['twse_match'] = _compare_rows(chosen, twse, tolerance_close_pct)
                if yahoo:
                    cross['yahoo_match'] = _compare_rows(chosen, yahoo, tolerance_close_pct)

                if chosen.date < asof_date:
                    warnings.append(f'Non-trading day fallback: used {chosen.date.isoformat()} <= {asof_date.isoformat()}')

                return {
                    'success': True,
                    'source': 'TEJ',
                    'symbol_input': symbol,
                    'normalized': norm,
                    'asof': asof,
                    'trade_date': chosen.date.isoformat(),
                    'row': _row_to_dict(chosen),
                    'warnings': warnings,
                    'cross_checks': cross,
                    'request_params': params,
                }
            else:
                warnings.append('TEJ returned empty within range or no date <= asof. Falling back to TWSE/Yahoo.')
        except Exception as e:
            warnings.append(f'TEJ error: {e!r}')

    # 2) TWSE fallback
    twse_client = TWSEClient()
    try:
        trow = twse_client.get_latest_price_leq(norm['coid'], asof_date)
    except Exception as e:
        trow = None
        warnings.append(f'TWSE error: {e!r}')

    if trow:
        yahoo = None
        try:
            yahoo = _select_yahoo_latest_leq(norm['yahoo_ticker'], trow.date)
        except Exception as e:
            warnings.append(f'Yahoo cross-check warning: {e!r}')

        if yahoo:
            cross['yahoo_match'] = _compare_rows(
                PriceRow(trow.date, trow.open, trow.high, trow.low, trow.close, trow.volume),
                yahoo,
                tolerance_close_pct
            )
        if trow.date < asof_date:
            warnings.append(f'Non-trading day fallback: used {trow.date.isoformat()} <= {asof_date.isoformat()}')

        return {
            'success': True,
            'source': 'TWSE',
            'symbol_input': symbol,
            'normalized': norm,
            'asof': asof,
            'trade_date': trow.date.isoformat(),
            'row': {
                'date': trow.date.isoformat(),
                'open': trow.open,
                'high': trow.high,
                'low': trow.low,
                'close': trow.close,
                'volume': trow.volume,
            },
            'warnings': warnings,
            'cross_checks': cross,
            'request_params': {
                'endpoint': 'TWSE STOCK_DAY',
                'months': [twse_client._gregorian_yyyymm01(asof_date),
                           twse_client._gregorian_yyyymm01(asof_date.replace(day=1) - dt.timedelta(days=1))],
                'stockNo': norm['coid']
            },
        }

    # 3) Yahoo fallback
    yahoo = None
    try:
        yahoo = _select_yahoo_latest_leq(norm['yahoo_ticker'], asof_date)
    except Exception as e:
        warnings.append(f'Yahoo error: {e!r}')

    if yahoo:
        if yahoo.date < asof_date:
            warnings.append(f'Non-trading day fallback: used {yahoo.date.isoformat()} <= {asof_date.isoformat()}')
        return {
            'success': True,
            'source': 'Yahoo',
            'symbol_input': symbol,
            'normalized': norm,
            'asof': asof,
            'trade_date': yahoo.date.isoformat(),
            'row': _row_to_dict(yahoo),
            'warnings': warnings,
            'cross_checks': {},
            'request_params': {'ticker': norm['yahoo_ticker'], 'window_days': 30},
        }

    # All failed
    return {
        'success': False,
        'source': 'None',
        'symbol_input': symbol,
        'normalized': norm,
        'asof': asof,
        'trade_date': None,
        'row': None,
        'warnings': warnings + ['All sources empty or failed. Check coid, permissions, and date range.'],
        'cross_checks': {},
        'request_params': {},
    }


def _compare_rows(base: PriceRow, other: Optional[PriceRow], tol_pct: float) -> Dict[str, Any]:
    if not other:
        return {'match': False, 'reason': 'no other row'}
    if base.date != other.date:
        return {'match': False, 'reason': f'date mismatch {base.date} vs {other.date}',
                'base': _row_to_dict(base), 'other': _row_to_dict(other)}
    pct = abs(other.close - base.close) / base.close if base.close else 1.0
    return {
        'match': pct <= tol_pct,
        'close_diff_pct': pct,
        'base': _row_to_dict(base),
        'other': _row_to_dict(other)
    }
