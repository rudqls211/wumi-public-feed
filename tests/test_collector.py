import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import scripts_collect as feed

class FeedTests(unittest.TestCase):
    def test_fx_schema_and_units(self):
        sample = {"USD": 1300.25, "JPY": 8.83, "EUR": 1480.1, "CNY": 185.7}
        def fake(url):
            code = url.split("/rate/")[1].split("/")[0]
            return {"rate": sample[code], "date": "2026-10-30"}
        result = feed.collect_fx(fake)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(set(result["data"]), set(feed.CURRENCIES))
        self.assertEqual(result["source_at"], "2026-10-30")
        self.assertEqual(result["data"]["JPY"]["krw_per_unit"], 8.83)
        self.assertEqual(result["data"]["JPY"]["unit"], 1)

    def test_reject_invalid_rates(self):
        for bad in (-1, 0, 99999999):
            with self.assertRaises(ValueError):
                feed.collect_fx(lambda url: {"rate": bad, "date": "2026-10-30"})

    def test_invalid_fx_date_rejected(self):
        with self.assertRaises(ValueError):
            feed.collect_fx(lambda url: {"rate": 1300, "date": "yesterday"})

    def test_stock_license_off_no_api_requests(self):
        with mock.patch.dict(os.environ, {"TWELVEDATA_API_KEY": "PRIVATEKEY"}, clear=True):
            with mock.patch.object(feed, "fetch") as network:
                result = feed.collect_quotes({"public_quote_symbols": ["AAPL"]})
        network.assert_not_called()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["data"], {})
        self.assertNotIn("PRIVATEKEY", json.dumps(result))

    def test_stock_license_revoked_discards_old_public_values(self):
        with tempfile.TemporaryDirectory() as temp:
            old = feed.DIR
            try:
                feed.DIR = Path(temp)
                feed.write_json(feed.DIR / "quotes.json", feed.envelope("quotes", "ok", "old", {"AAPL": {"close": 500}}))
                with mock.patch.dict(os.environ, {"TWELVEDATA_API_KEY": "PRIVATEKEY"}, clear=True):
                    result = feed.collect_quotes({"public_quote_symbols": ["AAPL"]})
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["data"], {})
            finally:
                feed.DIR = old

    def test_dart_license_revoked_discards_old_public_values(self):
        with tempfile.TemporaryDirectory() as temp:
            old = feed.DIR
            try:
                feed.DIR = Path(temp)
                feed.write_json(feed.DIR / "dividends.json", feed.envelope("dividends", "ok", "old", {"kr_disclosures": {"12345678": []}}))
                with mock.patch.dict(os.environ, {"OPENDART_API_KEY": "PRIVATEKEY"}, clear=True):
                    result = feed.collect_kr_dividends({"dart_corp_codes": ["12345678"]})
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["data"], {})
            finally:
                feed.DIR = old

    def test_allowlists_reject_private_user_identifiers(self):
        with self.assertRaises(ValueError):
            feed.collect_quotes({"public_quote_symbols": ["user/email@example.com"]})
        with self.assertRaises(ValueError):
            feed.collect_dividends({"dart_corp_codes": ["user-ID"]})

    def test_failure_preserves_last_success(self):
        with tempfile.TemporaryDirectory() as temp:
            old_dir, old_config = feed.DIR, feed.CONFIG
            try:
                feed.DIR, feed.CONFIG = Path(temp) / "docs", Path(temp) / "config"
                feed.write_json(feed.CONFIG / "public_catalog.json", {
                    "public_quote_symbols": [], "dart_corp_codes": []})
                feed.write_json(feed.DIR / "fx.json", feed.envelope(
                    "fx", "ok", "Frankfurter", {"USD": {"krw_per_unit": 1322.52}}, "2026-10-28"))
                with mock.patch.object(feed, "collect_fx", side_effect=OSError("secret request detail")):
                    with mock.patch.dict(os.environ, {}, clear=True):
                        feed.main()
                saved = feed.read_json(feed.DIR / "fx.json")
                self.assertEqual(saved["status"], "stale")
                self.assertEqual(saved["source_at"], "2026-10-28")
                self.assertEqual(saved["data"]["USD"]["krw_per_unit"], 1322.52)
                self.assertNotIn("secret request detail", json.dumps(saved))
            finally:
                feed.DIR, feed.CONFIG = old_dir, old_config

    def test_observed_us_dates_keep_prior_event(self):
        import datetime as dt
        today = dt.datetime.now(dt.timezone.utc).date()
        previous_date = (today - dt.timedelta(days=70)).isoformat()
        next_date = (today + dt.timedelta(days=25)).isoformat()
        def record(date):
            return {"symbol": "KO", "as_of": today.isoformat(),
                    "next_ex_date": date, "next_pay_date": None,
                    "next_declared_amount_usd": None,
                    "annual_amount_usd": 2.12, "payment_frequency": "quarterly",
                    "source_url": "https://smarterdividends.com/stocks/KO",
                    "is_actual_receipt": False}
        with tempfile.TemporaryDirectory() as temp:
            old = feed.DIR
            try:
                feed.DIR = Path(temp)
                feed.write_json(feed.DIR / "dividends.json", feed.envelope(
                    "dividends", "ok", "SmarterDividends",
                    {"us_history": {"KO": [record(previous_date)]}}))
                with mock.patch.object(feed, "refresh_us_dividends",
                        return_value=({"KO": record(next_date)}, 1, 0)):
                    with mock.patch.object(feed, "collect_kr_dividends",
                            return_value={"status": "unavailable", "data": {}}):
                        value = feed.collect_dividends({"us_dividend_symbols": ["KO"]})
                archive = value["data"]["us_history"]["KO"]
                self.assertEqual({v["next_ex_date"] for v in archive},
                                 {previous_date, next_date})
                self.assertTrue(all(v["is_actual_receipt"] is False for v in archive))
            finally:
                feed.DIR = old

    def test_unreviewed_tax_is_not_served(self):
        current_year = feed.dt.datetime.now(feed.dt.timezone.utc).year
        with tempfile.TemporaryDirectory() as temp:
            old = feed.CONFIG
            try:
                feed.CONFIG = Path(temp)
                feed.write_json(feed.CONFIG / f"tax_policy_{current_year}.json", {
                    "year": current_year, "reviewed_by_operator": False})
                result = feed.collect_tax()
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["data"], {})
            finally:
                feed.CONFIG = old

    def test_no_holiday_key_does_not_fake_dates(self):
        with tempfile.TemporaryDirectory() as temp:
            old = feed.DIR
            try:
                feed.DIR = Path(temp)
                with mock.patch.dict(os.environ, {}, clear=True):
                    result = feed.collect_holidays()
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["data"], {})
            finally:
                feed.DIR = old

if __name__ == "__main__":
    unittest.main()
