#!/usr/bin/env python3
"""WUMI public data: no personal assets; never print secrets or external URL errors."""
import datetime as dt
import json
import os
import pathlib
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from scripts.us_dividends import refresh as refresh_us_dividends

ROOT = pathlib.Path(__file__).resolve().parent
DIR = ROOT / "docs" / "data"
CONFIG = ROOT / "config"
CURRENCIES = ("USD", "JPY", "EUR", "CNY")
DATASETS = ("fx", "quotes", "dividends", "tax_policy", "holidays")
MAX_REPLY = 1024 * 1024

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def fetch(url):
    req = Request(url, headers={"User-Agent": "WUMI-public-feed/2.0"})
    with urlopen(req, timeout=12) as response:
        raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            raise ValueError("response too large")
        return raw

def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)

def envelope(kind, status, provider, data, source_at=None, note=None):
    return dict(schema_version=1, dataset=kind, status=status,
                generated_at=now(), source_at=source_at,
                provider=provider, data=data, note=note)

def existing(kind):
    old = read_json(DIR / (kind + ".json"), {})
    if isinstance(old, dict) and old.get("schema_version") == 1 and old.get("dataset") == kind:
        return old
    return {}

def keep_or_unavailable(kind, provider, reason):
    old = existing(kind)
    if old.get("status") in ("ok", "stale") and isinstance(old.get("data"), dict) and old["data"]:
        old["status"] = "stale"
        old["checked_at"] = now()
        old["note"] = reason
        return old
    return envelope(kind, "unavailable", provider, {}, note=reason)

def collect_fx(fetcher=None):
    if fetcher is None:
        fetcher = lambda url: json.loads(fetch(url))
    rates = {}
    dates = []
    for currency in CURRENCIES:
        obj = fetcher(f"https://api.frankfurter.dev/v2/rate/{currency}/KRW")
        rate = float(obj["rate"])
        date = str(obj["date"])
        if not 0 < rate < 1000000 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("invalid public reference rate/date")
        rates[currency] = dict(currency=currency, krw_per_unit=round(rate, 6),
                               unit=1, source_at=date)
        dates.append(date)
    return envelope("fx", "ok", "Frankfurter daily reference rates", rates, min(dates))

def collect_quotes(catalog):
    symbols = list(dict.fromkeys(catalog.get("public_quote_symbols", [])))
    if len(symbols) > 20 or any(not isinstance(s, str) or not re.fullmatch(r"[A-Z0-9.\-]{1,15}", s) for s in symbols):
        raise ValueError("invalid public quote allowlist")
    # A free API subscription does NOT grant permission to redistribute prices.
    if os.getenv("QUOTE_PUBLIC_REDISPLAY_LICENSE_CONFIRMED") != "true":
        return envelope("quotes", "unavailable", "License-gated quote provider", {},
                        note="해외 종가 재배포 이용권 확인 전")
    key = os.getenv("TWELVEDATA_API_KEY", "")
    if not key or not symbols:
        return keep_or_unavailable("quotes", "Twelve Data", "시세 키 또는 공개 대상 종목 미설정")
    quotes = {}
    for i, symbol in enumerate(symbols):
        if i:
            time.sleep(9)
        url = "https://api.twelvedata.com/eod?" + urlencode({"symbol": symbol, "apikey": key})
        obj = json.loads(fetch(url))
        if obj.get("status") == "error":
            raise ValueError("quote provider unavailable")
        value = float(obj["close"])
        date = str(obj["datetime"])
        if not 0 < value < 100000000 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("invalid closing price/date")
        quotes[symbol] = dict(close=round(value, 6), currency=str(obj.get("currency") or "USD"),
                              source_at=date, kind="EOD")
    return envelope("quotes", "ok", "Licensed EOD reference", quotes,
                    min(q["source_at"] for q in quotes.values()))

def collect_kr_dividends(catalog):
    companies = list(dict.fromkeys(catalog.get("dart_corp_codes", [])))
    if len(companies) > 12 or any(not isinstance(c, str) or not re.fullmatch(r"\d{8}", c) for c in companies):
        raise ValueError("invalid public DART allowlist")
    if os.getenv("DART_PUBLIC_REDISPLAY_LICENSE_CONFIRMED") != "true":
        return envelope("dividends", "unavailable", "OpenDART (redisplay review)", {},
                        note="국내 공시 재제공 이용조건 확인 전. 해외 배당 미연동")
    key = os.getenv("OPENDART_API_KEY", "")
    if not key or not companies:
        return keep_or_unavailable("dividends", "OpenDART", "공시 API 키 또는 공개 대상 기업 미설정")
    year = dt.datetime.now(dt.timezone.utc).year - 1
    items = {}
    for corp in companies:
        url = "https://opendart.fss.or.kr/api/alotMatter.json?" + urlencode({
            "crtfc_key": key, "corp_code": corp, "bsns_year": year, "reprt_code": "11011"})
        obj = json.loads(fetch(url))
        if obj.get("status") == "013":
            continue
        if obj.get("status") != "000":
            raise ValueError("DART data unavailable")
        rows = obj.get("list", [])
        items[corp] = [dict(company=str(r.get("corp_name", ""))[:90],
                            field=str(r.get("se", ""))[:110],
                            stock_type=str(r.get("stock_knd", ""))[:30],
                            reported_current=str(r.get("thstrm", ""))[:100],
                            report_year=year,
                            filing_no=str(r.get("rcept_no", ""))[:20],
                            payment_date=None, ex_date=None)
                       for r in rows[:40] if isinstance(r, dict)]
    if not items:
        return keep_or_unavailable("dividends", "OpenDART", "공시 결과 없음")
    return envelope("dividends", "ok", "OpenDART published annual filings",
                    {"kr_disclosures": items, "us_payment_history": {}}, str(year))

def collect_dividends(catalog):
    """Public fixed-list US dividend reference + separately licensed DART data.

    No user holdings or positions are transmitted. Null means not announced,
    never estimated. US data requires attribution to the provider.
    """
    old_data = existing("dividends").get("data", {})
    if not isinstance(old_data, dict):
        old_data = {}
    symbols = catalog.get("us_dividend_symbols", [])
    us, fresh = refresh_us_dividends(symbols, old_data.get("us"))
    kr = collect_kr_dividends(catalog)
    kr_data = kr.get("data", {}) if isinstance(kr, dict) else {}
    result_data = {}
    if us:
        result_data["us"] = us
        result_data["attribution"] = "US dividend reference data by SmarterDividends"
        result_data["source_url"] = "https://smarterdividends.com/dividend-api"
    if kr.get("status") in ("ok", "stale") and isinstance(kr_data, dict):
        disclosures = kr_data.get("kr_disclosures")
        if isinstance(disclosures, dict) and disclosures:
            result_data["kr_disclosures"] = disclosures
    if not result_data:
        return keep_or_unavailable("dividends", "SmarterDividends / OpenDART", "미국 배당 자료를 아직 받지 못했어요.")
    latest = max((x.get("as_of", "") for x in us.values() if isinstance(x, dict)), default="")
    return envelope("dividends", "ok" if fresh or kr.get("status") == "ok" else "stale",
                    "SmarterDividends (US reference) / OpenDART (KR license-gated)",
                    result_data, latest or None,
                    note="미국 종목별 무료 참고 정보. 출처 링크를 함께 확인하세요. 개별 지급 금액·지급일은 공란일 수 있어요.")

def collect_tax():
    year = dt.datetime.now(dt.timezone.utc).year
    value = read_json(CONFIG / f"tax_policy_{year}.json", {})
    if not isinstance(value, dict) or value.get("year") != year:
        return keep_or_unavailable("tax_policy", "Reviewed annual policy", "해당 연도 세법 기준 미등록")
    if value.get("reviewed_by_operator") is not True:
        return envelope("tax_policy", "unavailable", "Reviewed annual policy", {},
                        note="세법·소득공제 기준 검증 전. 앱 계산 변경 없음")
    keys = ("year", "pension_savings_credit_cap_krw", "pension_combined_credit_cap_krw",
            "housing_subscription_income_deduction_contribution_cap_krw",
            "housing_subscription_income_deduction_rate",
            "housing_subscription_salary_threshold_krw")
    validated = {key: value[key] for key in keys}
    validated["reviewed"] = True
    return envelope("tax_policy", "ok", "Operator-reviewed annual tax limits",
                    validated, str(value["reviewed_at"]))

def collect_holidays():
    year = dt.datetime.now(dt.timezone.utc).year
    old = existing("holidays")
    if old.get("status") == "ok" and old.get("source_at") == str(year) and old.get("data"):
        return old
    key = os.getenv("KASI_SERVICE_KEY", "")
    if not key:
        return keep_or_unavailable("holidays", "KASI special days", "공휴일 API 키 미등록")
    rows = {}
    for target in (year, year + 1):
        url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo?" + urlencode({
            "serviceKey": key, "solYear": target, "numOfRows": 200, "pageNo": 1})
        root = ET.fromstring(fetch(url))
        if root.findtext(".//resultCode") not in ("00", "0000"):
            raise ValueError("holiday source unavailable")
        for item in root.findall(".//item"):
            date = item.findtext("locdate", "")
            if not re.fullmatch(r"\d{8}", date) or item.findtext("isHoliday", "") != "Y":
                continue
            rows[f"{date[:4]}-{date[4:6]}-{date[6:8]}"] = (item.findtext("dateName") or "공휴일")[:60]
    if not rows:
        return keep_or_unavailable("holidays", "KASI", "공휴일 조회 결과 없음")
    return envelope("holidays", "ok", "KASI government special days", rows, str(year))

def main():
    catalog = read_json(CONFIG / "public_catalog.json")
    if not isinstance(catalog, dict):
        raise SystemExit("Public allowlist missing")
    jobs = (("fx", collect_fx),
            ("quotes", lambda: collect_quotes(catalog)),
            ("dividends", lambda: collect_dividends(catalog)),
            ("tax_policy", collect_tax),
            ("holidays", collect_holidays))
    for kind, job in jobs:
        try:
            value = job()
        except Exception:
            # Do not include external exception text: request URLs may contain API keys.
            value = keep_or_unavailable(kind, "External public-data source",
                                        "외부 제공처 응답 오류. 마지막 정상 자료 유지")
        write_json(DIR / (kind + ".json"), value)
        print(f"{kind}: {value['status']}")
    write_json(DIR / "index.json", envelope("index", "ok", "WUMI shared data",
                {kind: kind + ".json" for kind in DATASETS}))

if __name__ == "__main__":
    main()
