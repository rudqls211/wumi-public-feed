import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.build_holidays import render_year, publish

def fake_holidays(country, years, language):
    assert country == "KR"
    assert language == "ko"
    year = years[0]
    return {dt.date(year, 1, 1): "신정",
            dt.date(year, 3, 1): "삼일절"}

class HolidayGeneratorTests(unittest.TestCase):
    def test_dart_contract(self):
        data = render_year(2026, factory=fake_holidays)
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["holidays"][0],
                         {"date": "2026-01-01", "name": "신정"})
        self.assertEqual(len(data["holidays"]), 2)

    def test_publish_and_legacy_envelope(self):
        with TemporaryDirectory() as folder:
            publish(today=dt.date(2026, 10, 31),
                    output_root=folder, factory=fake_holidays)
            year = json.loads((Path(folder) / "holidays" / "2026.json").read_text())
            legacy = json.loads((Path(folder) / "data" / "holidays.json").read_text())
            self.assertEqual(year["year"], 2026)
            self.assertEqual(legacy["status"], "ok")
            self.assertEqual(legacy["data"]["2027-01-01"], "신정")
            self.assertTrue((Path(folder) / "holidays" / "2029.json").is_file())

    def test_reject_empty_calendar_without_deleting_last_snapshot(self):
        with self.assertRaises(ValueError):
            render_year(2026, factory=lambda *a, **k: {})
        with self.assertRaises(ValueError):
            render_year(1900, factory=fake_holidays)

if __name__ == "__main__":
    unittest.main()
