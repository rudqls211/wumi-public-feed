"""Attributed US dividend reference for a fixed public list, never users' holdings."""
import datetime as dt
import json
import math
import re
from urllib.request import Request, urlopen

API = "https://smarterdividends.com/api/v1/stocks/"
SOURCE = "SmarterDividends"
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,11}$")
MAX_SYMBOLS = 16

def strict_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        return None

def positive(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0 < number < 100000 else None

def parse_dividend(symbol, data):
    if not isinstance(data, dict) or str(data.get("symbol", "")).upper() != symbol:
        return None
    item = data.get("dividend")
    if not isinstance(item, dict):
        return None
    as_of = strict_date(data.get("as_of"))
    if not as_of:
        return None
    ex_date = strict_date(item.get("next_ex_date"))
    pay_date = strict_date(item.get("next_pay_date")) or strict_date(item.get("next_payment_date"))
    amount = positive(item.get("next_amount")) or positive(item.get("next_dividend_amount"))
    annual = positive(item.get("annual_amount"))
    frequency = str(item.get("frequency") or "").strip().lower()
    if frequency not in ("monthly", "quarterly", "semiannual", "semi-annually", "annual", "annually", "yearly", "weekly"):
        frequency = None
    if not ex_date and not pay_date:
        return None
    return {
        "symbol": symbol, "as_of": as_of, "next_ex_date": ex_date,
        "next_pay_date": pay_date, "next_declared_amount_usd": amount,
        "annual_amount_usd": annual, "payment_frequency": frequency,
        "source_url": f"https://smarterdividends.com/stocks/{symbol}",
        "source": SOURCE, "date_status": "provider_reported",
        "is_actual_receipt": False,
    }

def fetch_profile(symbol):
    req = Request(API + symbol, headers={
        "User-Agent": "WUMI-public-feed/1.1 (attributed public reference)",
        "Accept": "application/json",
    })
    with urlopen(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError("provider response error")
        content = response.read(131073)
    if len(content) > 131072:
        raise ValueError("provider response too large")
    return json.loads(content)

def refresh(symbols, previous=None, fetcher=fetch_profile, *, today=None):
    if not isinstance(symbols, list) or len(symbols) > MAX_SYMBOLS or len(set(symbols)) != len(symbols):
        raise ValueError("invalid public symbol list")
    if any(not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol) for symbol in symbols):
        raise ValueError("invalid public symbol code")
    old = previous if isinstance(previous, dict) else {}
    today = today or dt.datetime.now(dt.timezone.utc).date()
    data = {}
    fresh = 0
    failed = 0
    for symbol in symbols:
        try:
            parsed = parse_dividend(symbol, fetcher(symbol))
            if parsed is None:
                continue
            age = (today - dt.date.fromisoformat(parsed["as_of"])).days
            if age < -2 or age > 14:
                raise ValueError("invalid provider as-of age")
            data[symbol] = parsed
            fresh += 1
        except Exception:
            failed += 1
            prior = old.get(symbol)
            if isinstance(prior, dict) and prior.get("symbol") == symbol and (
                prior.get("source_url") == f"https://smarterdividends.com/stocks/{symbol}"
            ) and strict_date(prior.get("as_of")):
                age = (today - dt.date.fromisoformat(prior["as_of"])).days
                if 0 <= age <= 35:
                    data[symbol] = {**prior, "stale": True}
    return data, fresh, failed
