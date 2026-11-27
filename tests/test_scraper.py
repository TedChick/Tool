"""Unit tests for scraper parsing, filtering, and exporting."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scraper import export_csv, export_json, filter_matches, parse_espn_events, parse_youtube_live_html

SAMPLE_ESPN_PAYLOAD = {
    "leagues": [{"name": "English Premier League"}],
    "events": [
        {
            "id": "101",
            "name": "Arsenal vs Chelsea",
            "date": "2026-11-27T14:00Z",
            "status": {
                "displayClock": "67'",
                "type": {"state": "in", "shortDetail": "67'"},
            },
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "2",
                            "team": {"displayName": "Arsenal"},
                        },
                        {
                            "homeAway": "away",
                            "score": "1",
                            "team": {"displayName": "Chelsea"},
                        },
                    ],
                    "broadcasts": [{"names": ["K+ SPORT1", "Peacock"]}],
                }
            ],
            "links": [
                {"text": "Gamecast", "href": "https://www.espn.com/soccer/match/_/gameId/101"},
                {"text": "Watch", "href": "https://www.espn.com/watch/player/_/id/101"},
            ],
        },
        {
            "id": "102",
            "name": "Vietnam vs Thailand",
            "date": "2026-11-27T19:00Z",
            "status": {
                "type": {"state": "pre", "shortDetail": "19:00"},
            },
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "0",
                            "team": {"displayName": "Vietnam"},
                        },
                        {
                            "homeAway": "away",
                            "score": "0",
                            "team": {"displayName": "Thailand"},
                        },
                    ],
                    "broadcasts": [{"names": ["VTV5", "FPT Play"]}],
                }
            ],
            "links": [
                {"text": "Match Page", "href": "https://www.espn.com/soccer/match/_/gameId/102"},
            ],
        },
    ],
}


class ScraperTests(unittest.TestCase):
    def test_parse_espn_events(self) -> None:
        matches = parse_espn_events(SAMPLE_ESPN_PAYLOAD)
        self.assertEqual(len(matches), 2)

        live_match = matches[0]
        self.assertEqual(live_match.status, "live")
        self.assertEqual(live_match.score, "2 - 1")
        self.assertEqual(live_match.broadcasts, ["K+ SPORT1", "Peacock"])
        self.assertEqual(len(live_match.links), 2)

        upcoming_match = matches[1]
        self.assertEqual(upcoming_match.status, "upcoming")
        self.assertEqual(upcoming_match.home_team, "Vietnam")

    def test_filter_matches(self) -> None:
        matches = parse_espn_events(SAMPLE_ESPN_PAYLOAD)

        only_live = filter_matches(matches, live_only=True)
        self.assertEqual(len(only_live), 1)
        self.assertEqual(only_live[0].id, "101")

        by_channel = filter_matches(matches, query="FPT Play")
        self.assertEqual(len(by_channel), 1)
        self.assertEqual(by_channel[0].id, "102")

    def test_export_json_and_csv(self) -> None:
        matches = parse_espn_events(SAMPLE_ESPN_PAYLOAD)
        with tempfile.TemporaryDirectory() as tmp:
            json_path = export_json(matches, Path(tmp) / "out.json")
            csv_path = export_csv(matches, Path(tmp) / "out.csv")

            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["name"], "Arsenal vs Chelsea")

            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertIn("K+ SPORT1", rows[0]["broadcasts"])

    def test_parse_youtube_live_html(self) -> None:
        sample_html = (
            '<html><script>var ytInitialData = {"contents": [{"videoRenderer": '
            '{"videoId": "abc123xyz", "title": {"runs": [{"text": "Live Match Stream"}]}, '
            '"ownerText": {"runs": [{"text": "Official Sports"}]}, '
            '"viewCountText": {"runs": [{"text": "1,200 watching"}]}}}]};</script></html>'
        )
        streams = parse_youtube_live_html(sample_html)
        self.assertEqual(len(streams), 1)
        self.assertEqual(streams[0]["video_id"], "abc123xyz")
        self.assertEqual(streams[0]["channel"], "Official Sports")
        self.assertIn("youtube.com/embed/abc123xyz", streams[0]["embed_url"])


if __name__ == "__main__":
    unittest.main()
