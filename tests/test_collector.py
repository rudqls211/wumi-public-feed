import unittest
import scripts_collect as feed

class FeedTests(unittest.TestCase):
    def test_fx_schema(self):
        def fake(url):
            return {"rate": 1300.25, "date": "2026-10-30"}
        result = feed.collect_fx(fake)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(set(result["data"]), set(feed.CURRENCIES))
        self.assertEqual(result["data"]["USD"]["krw_per_unit"], 1300.25)

    def test_reject_invalid_rates(self):
        with self.assertRaises(ValueError):
            feed.collect_fx(lambda url: {"rate": -1, "date": "2026-10-30"})

if __name__ == "__main__":
    unittest.main()
