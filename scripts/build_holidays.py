#!/usr/bin/env python3
"""Build PUBLIC South Korean holidays for WUMI. No API key or user data.

Calculated holidays are not an official announcement feed: newly declared
temporary holidays and election-day exceptions must be checked separately.
The calendar widget must never include investment/dividend payment forecasts.
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROVIDER = "python-holidays (KR rule-based calendar)"



def display_name(name):
    """Prefer familiar Korean calendar labels; never modify the holiday date."""
    text = str(name).strip()
    replacements = {
        "기독탄신일": "크리스마스",
        "성탄절": "크리스마스",
        "신정연휴": "신정",
        "설날 전날": "설날 연휴",
        "설날 다음날": "설날 연휴",
        "추석 전날": "추석 연휴",
        "추석 다음날": "추석 연휴",
        "부처님오신날": "부처님 오신 날",
        "대체 휴일": "대체공휴일",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text

def render_year(year, factory=None):
    if not 2000 <= year <= 2100:
        raise ValueError("year outside supported publishing range")
    if factory is None:
        import holidays
        factory = holidays.country_holidays
    source = factory("KR", years=[year], language="ko")
    rows = []
    for date, name in sorted(source.items()):
        if date.year != year:
            continue
        label = display_name(name)
        if not label or len(label) > 70:
            raise ValueError("invalid holiday name")
        rows.append({"date": date.isoformat(), "name": label})
    if not rows:
        raise ValueError("holiday source returned an empty year")
    return {
        "schema_version": 1,
        "year": year,
        "holidays": rows,
        "source": PROVIDER,
        "note": "법령 기반 계산값. 임시공휴일·선거일 등은 공식 발표와 대조 필요",
    }


def publish(today=None, output_root=None, factory=None):
    today = today or dt.date.today()
    output_root = Path(output_root) if output_root else DOCS
    years = range(today.year - 1, today.year + 4)
    # Build all before writing. On source failure, existing published files survive.
    by_year = {year: render_year(year, factory=factory) for year in years}
    combined = {}
    for year in (today.year, today.year + 1):
        for item in by_year[year]["holidays"]:
            combined[item["date"]] = item["name"]
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    overview = {
        "schema_version": 1, "dataset": "holidays", "status": "ok",
        "generated_at": stamp, "source_at": str(today.year),
        "provider": PROVIDER, "data": combined,
        "note": "법령 기반 자동 생성. 임시공휴일·선거일은 공적 발표와 대조 필요",
    }
    for year, payload in by_year.items():
        target = output_root / "holidays" / f"{year}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = output_root / "data" / "holidays.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(overview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"holidays: {len(combined)} days, years {min(years)}-{max(years)}")
    return by_year


if __name__ == "__main__":
    publish()
