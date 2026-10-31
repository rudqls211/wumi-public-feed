import datetime as dt
import unittest

from scripts.us_public_dividends import parse_dividend, refresh

TODAY = dt.date(2026, 10, 31)

def example(symbol="SCHD", ex="2026-11-19"):
    return {"symbol": symbol, "as_of": "2026-10-30", "dividend": {
        "next_ex_date": ex, "annual_amount": 1.12}}

class UsPublicDividendTests(unittest.TestCase):
    def test_ex_date_without_invented_payment(self):
        item = parse_dividend("SCHD", example())
        self.assertEqual(item["next_ex_date"], "2026-11-19")
        self.assertIsNone(item["next_pay_date"])
        self.assertIsNone(item["next_declared_amount_usd"])
        self.assertFalse(item["is_actual_receipt"])

    def test_provider_declared_payment_and_amount(self):
        value = example()
        value["dividend"].update(next_pay_date="2026-11-25", next_amount=0.27)
        item = parse_dividend("SCHD", value)
        self.assertEqual(item["next_pay_date"], "2026-11-25")
        self.assertEqual(item["next_declared_amount_usd"], 0.27)

    def test_wrong_symbol_and_impossible_date(self):
        self.assertIsNone(parse_dividend("SCHD", example(symbol="MSFT")))
        self.assertIsNone(parse_dividend("SCHD", example(ex="2026-02-31")))

    def test_failed_call_keeps_valid_old_date(self):
        old = {"SCHD": parse_dividend("SCHD", example())}
        data, fresh, failed = refresh(["SCHD"], old, fetcher=lambda _: 1 / 0, today=TODAY)
        self.assertEqual(fresh, 0)
        self.assertEqual(failed, 1)
        self.assertTrue(data["SCHD"]["stale"])

    def test_does_not_publish_invalid_or_user_specific_symbols(self):
        for symbol in ("005930", "USER@EXAMPLE.COM", "SCHD.MX/2"):
            with self.assertRaises(ValueError):
                refresh([symbol], today=TODAY)
        with self.assertRaises(ValueError):
            refresh(["SCHD", "SCHD"], today=TODAY)

    def test_provider_frequency_is_explicit_not_guessed(self):
        raw = example()
        raw["dividend"]["frequency"] = "quarterly"
        item = parse_dividend("SCHD", raw)
        self.assertEqual(item["payment_frequency"], "quarterly")
        raw["dividend"]["frequency"] = "surprise"
        self.assertIsNone(parse_dividend("SCHD", raw)["payment_frequency"])

    def test_nonpayer_is_not_a_zero_dividend_receipt(self):
        data, fresh, failed = refresh(["IONQ"],
            fetcher=lambda _: {"symbol": "IONQ", "as_of": "2026-10-30", "dividend": {}},
            today=TODAY)
        self.assertEqual(data, {})
        self.assertEqual(fresh, 0)
        self.assertEqual(failed, 0)

if __name__ == "__main__":
    unittest.main()
