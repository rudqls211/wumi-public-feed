import json
from pathlib import Path
import tempfile
import unittest
from scripts.build_us_sec_directory import parse_sec, build

SAMPLE = json.dumps({"fields":["cik","name","ticker","exchange"],"data":[
    [320193,"Apple Inc.","AAPL","Nasdaq"],
    [789019,"Microsoft Corporation","MSFT","Nasdaq"],
    [2,"OTC Co","OTCX","OTC"],
    [3,"Bad Code","BAD/TICKER","NYSE"],
    [4,"Dup","AAPL","NYSE"]]}).encode()

class SECDirectoryTest(unittest.TestCase):
    def test_filter_and_validation(self):
        rows = parse_sec(SAMPLE, min_count=2)
        self.assertEqual([x["symbol"] for x in rows], ["AAPL","MSFT"])
        self.assertEqual(rows[0]["name"], "Apple Inc.")
        with self.assertRaises(ValueError): parse_sec(SAMPLE)
        with self.assertRaises(ValueError): parse_sec(b"{}")

    def test_fail_safe_no_previous_file_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "directory.json"
            self.assertEqual(build(fetcher=lambda: SAMPLE, output=path, min_count=2), 2)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                build(fetcher=lambda: b"{}", output=path, min_count=2)
            self.assertEqual(path.read_bytes(), before)
            value = json.loads(before)
            self.assertEqual(value["dataset"], "stock_directory_us")
            self.assertFalse(any("price" in r or "account" in r for r in value["entries"]))

if __name__ == "__main__": unittest.main()
