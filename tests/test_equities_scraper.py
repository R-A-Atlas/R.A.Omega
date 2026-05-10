from __future__ import annotations

from atlas_agents.equities import equities_scraper


def test_equities_scraper_shapes_yahoo_screens(monkeypatch):
    payloads = {
        "day_gainers": [
            {
                "symbol": "ABC",
                "shortName": "ABC Corp",
                "regularMarketPrice": 12.5,
                "regularMarketChangePercent": 8.1,
                "regularMarketVolume": 1000000,
            }
        ],
        "day_losers": [
            {
                "symbol": "XYZ",
                "shortName": "XYZ Inc",
                "regularMarketPrice": 9.2,
                "regularMarketChangePercent": -6.4,
                "regularMarketVolume": 900000,
            }
        ],
        "most_actives": [
            {
                "symbol": "ABC",
                "shortName": "ABC Corp",
                "regularMarketPrice": 12.5,
                "regularMarketChangePercent": 8.1,
                "regularMarketVolume": 5000000,
            },
            {
                "symbol": "VOL",
                "shortName": "Volume Co",
                "regularMarketPrice": 2.0,
                "regularMarketChangePercent": 1.2,
                "regularMarketVolume": 8000000,
            },
        ],
    }

    def fake_get_json(_url, *, params=None, **_kwargs):
        screen = params["scrIds"]
        return {"finance": {"result": [{"quotes": payloads[screen]}]}}

    monkeypatch.setattr(equities_scraper, "requests_get_json", fake_get_json)

    out = equities_scraper.scrape(count_per_bucket=5)
    assert out["source"] == "yahoo_finance_public_screener"
    assert out["record_count"] == 3
    assert out["gainers"][0]["signal"] == "BULLISH_MOMENTUM"
    assert out["losers"][0]["signal"] == "BEARISH_MOMENTUM"
    assert out["active"][0]["signal"] == "HIGH_ACTIVITY"
    assert [r["ticker"] for r in out["combined"]] == ["ABC", "XYZ", "VOL"]


def test_equities_write_outputs_uses_cache_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(equities_scraper, "DATA_CACHE_DIR", tmp_path)
    stable, stamped = equities_scraper.write_outputs(
        {
            "generated_at": "2026-05-10T00:00:00Z",
            "source": "test",
            "record_count": 0,
            "gainers": [],
            "losers": [],
            "active": [],
            "combined": [],
        }
    )
    assert stable.name == "equities_latest.json"
    assert stamped.name.startswith("equities_")
    assert stable.exists()
    assert stamped.exists()
