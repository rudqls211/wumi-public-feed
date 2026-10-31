#!/usr/bin/env python3
"""SEC public ticker/company-name directory. English, not quotes or Korean translations."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

URL = "https://www.sec.gov/files/company_tickers_exchange.json"
DEST = Path(__file__).resolve().parents[1] / "docs/stocks/us_sec_directory_v1.json"
EXCHANGES = {"Nasdaq", "NYSE", "NYSE American", "NYSE Arca", "Cboe BZX", "CBOE", "NYSE MKT"}
CODE = re.compile(r"[A-Z][A-Z0-9.\-]{0,11}\Z")

def parse_sec(raw, min_count=1500):
    if len(raw) > 5_000_000: raise ValueError("oversized SEC response")
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("fields"), list) or not isinstance(doc.get("data"), list):
        raise ValueError("not an SEC directory")
    keys = doc["fields"]
    if not {"ticker", "name", "exchange"} <= set(keys): raise ValueError("SEC fields missing")
    ti, ni, ei = (keys.index(x) for x in ("ticker", "name", "exchange"))
    symbols = {}
    for row in doc["data"]:
        if not isinstance(row, list) or len(row) != len(keys): continue
        symbol, name, exchange = (row[j] for j in (ti, ni, ei))
        if not isinstance(symbol, str) or not isinstance(name, str) or exchange not in EXCHANGES: continue
        symbol, name = symbol.strip().upper(), name.strip()
        if not CODE.fullmatch(symbol) or not 1 <= len(name) <= 180 or not name.isprintable(): continue
        if symbol not in symbols:
            symbols[symbol] = {"market": "US", "symbol": symbol, "name": name, "exchange": exchange}
    if not min_count <= len(symbols) <= 20_000:
        raise ValueError("unexpected SEC directory count: " + str(len(symbols)))
    return [symbols[k] for k in sorted(symbols)]

def build(fetcher=None, output=DEST, min_count=1500):
    if fetcher is None:
        def fetcher():
            request = Request(URL, headers={
                "User-Agent": "WUMI-PublicFeed/1.0 (https://github.com/rudqls211/wumi-public-feed)",
                "Accept": "application/json"})
            with urlopen(request, timeout=20) as response:
                return response.read(5_000_001)
    entries = parse_sec(fetcher(), min_count=min_count)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    doc = {"schema_version": 1, "dataset": "stock_directory_us",
           "source": "U.S. Securities and Exchange Commission (SEC)", "source_url": URL,
           "retrieved_at": stamp, "note": "Official English ticker names, not Korean translations or prices; SEC does not guarantee accuracy or scope.",
           "entries": entries}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".tmp", dir=output.parent, delete=False) as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
        tmp = Path(f.name)
    try:
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)
    return len(entries)

if __name__ == "__main__":
    try:
        count = build()
        print(f"US SEC directory: {count} English company names")
    except Exception as exc:
        print(f"US SEC directory unavailable ({type(exc).__name__}); last snapshot preserved")
