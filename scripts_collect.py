#!/usr/bin/env python3
"""WUMI public reference feed: public FX only until redistribution rights reviewed."""
import datetime as dt
import json
import pathlib
import re
from urllib.request import Request, urlopen

ROOT = pathlib.Path(__file__).resolve().parent
DIR = ROOT / "docs" / "data"
CURRENCIES = ("USD", "JPY", "EUR", "CNY")

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def read(name):
    try:
        return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}

def write(name, payload):
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f"{name}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)

def envelope(kind, status, provider, data, source_at=None, note=None):
    return dict(schema_version=1, dataset=kind, status=status, generated_at=now(),
                source_at=source_at, provider=provider, data=data, note=note)

def collect_fx(fetcher=None):
    if fetcher is None:
        def fetcher(url):
            req = Request(url, headers={"User-Agent": "WUMI-public-feed/1.0"})
            with urlopen(req, timeout=12) as response:
                raw = response.read(16385)
                if len(raw) > 16384:
                    raise ValueError("response too large")
                return json.loads(raw)
    data = {}
    dates = []
    for currency in CURRENCIES:
        item = fetcher(f"https://api.frankfurter.dev/v2/rate/{currency}/KRW")
        rate, date = float(item["rate"]), str(item["date"])
        if not 0 < rate < 1000000 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("invalid FX rate or date")
        data[currency] = dict(currency=currency, krw_per_unit=round(rate, 6), unit=1, source_at=date)
        dates.append(date)
    return envelope("fx", "ok", "Frankfurter daily reference rates", data, min(dates))

def main():
    old = read("fx")
    try:
        result = collect_fx()
    except Exception:
        if old.get("status") in ("ok", "stale") and old.get("data"):
            result = dict(old, status="stale", checked_at=now(), note="환율 서버 연결 실패: 마지막 정상 자료 유지")
        else:
            result = envelope("fx", "unavailable", "Frankfurter", {}, note="환율 서버 연결 실패: 아직 저장된 자료 없음")
    write("fx", result)
    for kind, provider, note in [
        ("quotes", "License-gated provider", "시세 재배포 권한 확인 전"),
        ("dividends", "OpenDART / licensed provider", "공시 API 또는 배당 공개 조건 미설정"),
        ("tax_policy", "Operator reviewed policy", "세법 기준 검증 전"),
        ("holidays", "KASI special days", "공휴일 API 인증 및 연도별 검증 전"),
    ]:
        previous = read(kind)
        if previous.get("status") == "ok" and previous.get("data"):
            continue
        write(kind, envelope(kind, "unavailable", provider, {}, note=note))
    write("index", envelope("index", "ok", "WUMI shared data", {
        name: name + ".json" for name in ("fx", "quotes", "dividends", "tax_policy", "holidays")
    }))
    print("Public feed updated. FX status:", result["status"], "source date:", result.get("source_at"))

if __name__ == "__main__":
    main()
