"""Small, public, attributed US dividend snapshots from a keyless lookup API.
No price feed, no per-user holdings, no dividend-date inference.
"""
import datetime as dt
import json
import math
import re
from urllib.request import Request, urlopen

API = 'https://smarterdividends.com/api/v1/stocks/'
SYMBOL_PATTERN = re.compile(r'[A-Z][A-Z0-9.\-]{0,11}\Z')
DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}\Z')

def valid_date(value):
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return None
    try:
        dt.date.fromisoformat(value)
        return value
    except ValueError:
        return None

def valid_number(value, *, allow_zero=False, maximum=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    val = float(value)
    if not math.isfinite(val) or val < 0 or (val == 0 and not allow_zero) or val > maximum:
        return None
    return val

def default_fetch(url):
    req = Request(url, headers={'User-Agent': 'WUMI Public Reference Feed (github.com/rudqls211/wumi-public-feed)'})
    with urlopen(req, timeout=10) as response:
        content = response.read(262145)
    if len(content) > 262144:
        raise ValueError('too-large response')
    return json.loads(content)

def parse_profile(ticker, raw):
    """Only quote a few facts with an explicit provider attribution link."""
    if not isinstance(raw, dict) or raw.get('symbol', '').upper() != ticker:
        raise ValueError('wrong ticker')
    dividend = raw.get('dividend')
    if not isinstance(dividend, dict):
        raise ValueError('no dividend details')
    source_url = f'https://smarterdividends.com/stocks/{ticker}'
    ex_date = valid_date(dividend.get('next_ex_date'))
    pay_date = valid_date(dividend.get('next_pay_date'))
    if not pay_date:
        pay_date = valid_date(dividend.get('next_payment_date'))
    amount = valid_number(dividend.get('next_amount'))
    if amount is None:
        amount = valid_number(dividend.get('next_dividend_amount'))
    annual = valid_number(dividend.get('annual_amount'), allow_zero=True)
    forward_yield = valid_number(dividend.get('forward_yield'), allow_zero=True, maximum=100)
    as_of = valid_date(raw.get('as_of'))
    if as_of is None:
        raise ValueError('no valid as-of date')
    if not any(v is not None for v in (ex_date, pay_date, amount, annual, forward_yield)):
        raise ValueError('no usable dividend fields')
    return {
        'symbol': ticker,
        'name': str(raw.get('name') or ticker)[:100],
        'as_of': as_of,
        'next_ex_date': ex_date,
        'next_pay_date': pay_date,
        'next_declared_amount_usd': amount,
        'annualized_dividend_usd': annual,
        'forward_yield': forward_yield,
        'source_url': source_url,
        'date_status': 'declared_or_provider_reported' if ex_date else 'not_published',
        'data_category': 'dividend_reference',
    }

def refresh(symbols, previous=None, fetcher=None):
    """Max eight unrelated public tickers, never account holdings. Partial failures keep last quoted facts."""
    if not isinstance(symbols, list) or len(symbols) > 8 or len(symbols) != len(set(symbols)):
        raise ValueError('public dividend allowlist invalid')
    if any(not isinstance(s, str) or not SYMBOL_PATTERN.fullmatch(s) for s in symbols):
        raise ValueError('public dividend symbol invalid')
    fetcher = fetcher or default_fetch
    old = previous if isinstance(previous, dict) else {}
    out = {}
    fresh = []
    for symbol in symbols:
        try:
            obj = parse_profile(symbol, fetcher(API + symbol))
            out[symbol] = obj
            fresh.append(symbol)
        except Exception:
            old_obj = old.get(symbol)
            if isinstance(old_obj, dict) and old_obj.get('symbol') == symbol and old_obj.get('source_url') == f'https://smarterdividends.com/stocks/{symbol}':
                out[symbol] = {**old_obj, 'stale': True}
    return out, fresh
