import json
from pathlib import Path
import re
import unittest

FILE = Path(__file__).resolve().parents[1] / "docs/stocks/ko_names_v1.json"

class StockNamesTests(unittest.TestCase):
    def test_schema_symbols_and_nonsecret_records(self):
        data = json.loads(FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["dataset"], "stock_names")
        seen = set()
        for row in data["entries"]:
            market, symbol = row["market"], row["symbol"]
            self.assertIn(market, ("US", "KR"))
            self.assertRegex(symbol, r"^([0-9]{6}|[A-Z][A-Z0-9.\\-]{0,11})$")
            self.assertNotIn((market, symbol), seen)
            seen.add((market, symbol))
            self.assertTrue(row["name_ko"].strip())
            self.assertIsInstance(row["aliases"], list)
            self.assertNotIn("price", row)
            self.assertNotIn("account", row)
            self.assertNotIn("uid", row)
        self.assertIn(("US","NVDA"), seen)
        self.assertIn(("KR","005930"), seen)

if __name__ == "__main__":
    unittest.main()
