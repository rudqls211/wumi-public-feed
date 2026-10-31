# WUMI public holiday and Korean-stock display feeds

- Calendar: `/holidays/YYYY.json`. App schema: `{"year":2026,"holidays":[{"date":"2026-01-01","name":"신정"}]}`. Only public Korean holidays; **no** dividend or payment dates.
- Legacy diagnostics: `/data/holidays.json` remains available.
- Korean stock-name aliases: `/stocks/ko_names_v1.json`. Curated for display/search, not an exchange master, quote feed or investment advice.
- If an entry is absent or a network request fails, the mobile app should retain its existing display name. Never overwrite the user's saved holding name, security code, position, price, or financial DB from this public list.
- Holiday calculations use the MIT-licensed `python-holidays` library, regenerated through GitHub Actions without an API key. Temporary holidays, election dates and changes announced by authorities require manual verification.
- Repository is PUBLIC. Never store private financial data, API keys, portfolio holdings or OAuth secrets here.
