import json
from pathlib import Path

from atlas_core.summaries.summary_generator import generate_all, summarize_cache


def test_summary_generator_creates_one_summary_per_latest_cache(tmp_path: Path):
    cache_dir = tmp_path / "data_cache"
    summary_dir = cache_dir / "summaries"
    cache_dir.mkdir()
    (cache_dir / "sample_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-13T00:00:00Z",
                "record_count": 2,
                "items": [
                    {"ticker": "AAA", "change_pct": 4.2, "volume": 1000},
                    {"ticker": "BBB", "change_pct": -2.1, "volume": 2000},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = generate_all(cache_dir, summary_dir)

    assert result["ok"] is True
    assert result["cache_files"] == 1
    assert result["summary_files"] == 1
    summary = json.loads((summary_dir / "sample_summary.json").read_text(encoding="utf-8"))
    assert summary["source_cache"] == "sample_latest.json"
    assert summary["top_signal"]["id"] == "AAA"


def test_equities_summary_uses_contract_shape(tmp_path: Path):
    path = tmp_path / "equities_latest.json"
    path.write_text(
        json.dumps(
            {
                "gainers": [{"ticker": "WIN", "change_pct": 12.5, "volume": 100, "sector": "Tech"}],
                "losers": [{"ticker": "LOSE", "change_pct": -8.0, "volume": 50, "sector": "Energy"}],
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_cache(path)

    assert set(summary) == {
        "generated_at",
        "top_gainer",
        "top_loser",
        "most_active",
        "hot_sector",
        "cold_sector",
        "breadth_signal",
    }
    assert summary["top_gainer"]["ticker"] == "WIN"
    assert summary["top_loser"]["ticker"] == "LOSE"

