"""Core module for fetching and parsing public live football match data and links."""

from __future__ import annotations

import concurrent.futures
import csv
import html.parser
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
)

SPORT_SOURCES = [
    ("all_sports", "Tất cả bộ môn (Bóng đá, NBA, Tennis, NHL, NFL, UFC...)"),
    ("soccer/all", "Bóng đá - Tất cả giải"),
    ("soccer/eng.1", "Bóng đá - Premier League"),
    ("soccer/uefa.champions", "Bóng đá - UEFA Champions League"),
    ("soccer/esp.1", "Bóng đá - La Liga"),
    ("basketball/nba", "Bóng rổ - NBA"),
    ("basketball/mens-college-basketball", "Bóng rổ - NCAA"),
    ("tennis/atp", "Tennis - ATP"),
    ("tennis/wta", "Tennis - WTA"),
    ("hockey/nhl", "Khúc côn cầu - NHL"),
    ("football/nfl", "Bóng bầu dục - NFL"),
    ("baseball/mlb", "Bóng chày - MLB"),
    ("mma/ufc", "Võ thuật - UFC"),
]

DEFAULT_LEAGUES = SPORT_SOURCES


@dataclass
class MatchInfo:
    """Normalized representation of a football match and its public links."""

    id: str
    league: str
    name: str
    home_team: str
    away_team: str
    score: str
    status: str  # "live" | "upcoming" | "finished"
    status_detail: str
    start_time: str
    broadcasts: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _AnchorExtractor(html.parser.HTMLParser):
    """Lightweight HTML parser to extract public anchor links and text."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attr_map = dict(attrs)
            href = attr_map.get("href")
            if href:
                self._current_href = href.strip()
                self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            text = " ".join("".join(self._text_parts).split())
            self.anchors.append((self._current_href, text))
            self._current_href = None
            self._text_parts = []


def _http_get_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _split_source(source: str) -> tuple[str, str]:
    clean = (source or "soccer/all").strip()
    if "/" in clean:
        sport, league = clean.split("/", 1)
        return sport or "soccer", league or "all"
    return "soccer", clean


def fetch_espn_scoreboard(league: str = "soccer/all", timeout: int = 15) -> dict[str, Any]:
    """Fetch public JSON scoreboard data from ESPN for a sport/league slug."""
    sport, league_slug = _split_source(league)
    safe_sport = urllib.parse.quote(sport, safe="-")
    safe_league = urllib.parse.quote(league_slug, safe=".-")
    url = ESPN_SCOREBOARD_URL.format(sport=safe_sport, league=safe_league)
    raw = _http_get_text(url, timeout=timeout)
    return json.loads(raw)


def fetch_all_sports_matches(timeout: int = 15) -> list[MatchInfo]:
    """Fetch matches across all configured sports concurrently."""
    targets = [
        slug
        for slug, _ in SPORT_SOURCES
        if slug != "all_sports" and not slug.startswith("soccer/") or slug == "soccer/all"
    ]
    all_matches: list[MatchInfo] = []
    seen_ids: set[str] = set()

    def _fetch_one(slug: str) -> list[MatchInfo]:
        try:
            data = fetch_espn_scoreboard(slug, timeout=timeout)
            return parse_espn_events(data)
        except Exception:  # noqa: BLE001
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for batch in pool.map(_fetch_one, targets):
            for m in batch:
                key = f"{m.league}:{m.id}:{m.name}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    all_matches.append(m)

    status_order = {"live": 0, "upcoming": 1, "finished": 2}
    all_matches.sort(key=lambda m: (status_order.get(m.status, 3), m.start_time))
    return all_matches


def _map_status(state: str) -> str:
    state_lower = (state or "").lower()
    if state_lower == "in":
        return "live"
    if state_lower == "post":
        return "finished"
    return "upcoming"


def parse_espn_events(data: dict[str, Any]) -> list[MatchInfo]:
    """Parse ESPN scoreboard JSON payload into a list of MatchInfo objects."""
    league_info = (data.get("leagues") or [{}])[0]
    default_league_name = league_info.get("name") or "Soccer"
    matches: list[MatchInfo] = []

    for event in data.get("events") or []:
        competitions = event.get("competitions") or []
        comp = competitions[0] if competitions else {}
        competitors = comp.get("competitors") or []

        home_team = ""
        away_team = ""
        home_score = "0"
        away_score = "0"

        for team_entry in competitors:
            team_name = (team_entry.get("team") or {}).get("displayName", "")
            team_score = str(team_entry.get("score", "0"))
            if team_entry.get("homeAway") == "home":
                home_team = team_name
                home_score = team_score
            elif team_entry.get("homeAway") == "away":
                away_team = team_name
                away_score = team_score

        status_obj = event.get("status") or comp.get("status") or {}
        status_type = status_obj.get("type") or {}
        status = _map_status(status_type.get("state", "pre"))
        status_detail = (
            status_type.get("shortDetail")
            or status_type.get("detail")
            or status_obj.get("displayClock")
            or ""
        )

        broadcasts: list[str] = []
        for bc in comp.get("broadcasts") or []:
            for name in bc.get("names") or []:
                if name and name not in broadcasts:
                    broadcasts.append(name)

        links: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for link in event.get("links") or []:
            href = (link.get("href") or "").strip()
            if href and href not in seen_urls:
                seen_urls.add(href)
                links.append(
                    {
                        "label": link.get("text") or link.get("shortText") or "Match Link",
                        "url": href,
                    }
                )

        score_str = f"{home_score} - {away_score}" if home_team and away_team else "-"
        league_name = (
            (event.get("season") or {}).get("slug")
            or default_league_name
        )
        # Prefer human-readable league name when available on the top-level payload
        if default_league_name and default_league_name != "Soccer":
            league_name = default_league_name

        matches.append(
            MatchInfo(
                id=str(event.get("id", "")),
                league=league_name,
                name=event.get("name") or f"{home_team} vs {away_team}",
                home_team=home_team,
                away_team=away_team,
                score=score_str,
                status=status,
                status_detail=status_detail,
                start_time=event.get("date") or "",
                broadcasts=broadcasts,
                links=links,
            )
        )

    status_order = {"live": 0, "upcoming": 1, "finished": 2}
    matches.sort(key=lambda m: (status_order.get(m.status, 3), m.start_time))
    return matches


def fetch_public_page_links(
    url: str, keywords: tuple[str, ...] = ("live", "truc-tiep", "trực tiếp", "football", "bong-da", "bóng đá", "watch", "match"),
    timeout: int = 15,
) -> list[dict[str, str]]:
    """Extract public anchor links matching football/live keywords from a given webpage URL."""
    html_text = _http_get_text(url, timeout=timeout)
    parser = _AnchorExtractor()
    parser.feed(html_text)

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    lower_keywords = tuple(k.lower() for k in keywords)

    for href, text in parser.anchors:
        full_url = urllib.parse.urljoin(url, href)
        if not full_url.startswith(("http://", "https://")):
            continue
        haystack = f"{full_url} {text}".lower()
        if any(kw in haystack for kw in lower_keywords) and full_url not in seen:
            seen.add(full_url)
            results.append({"label": text or full_url, "url": full_url})

    return results


def filter_matches(
    matches: list[MatchInfo],
    live_only: bool = False,
    query: str | None = None,
) -> list[MatchInfo]:
    """Filter matches by live status and/or keyword across team, league, and broadcasts."""
    filtered = matches
    if live_only:
        filtered = [m for m in filtered if m.status == "live"]

    if query:
        q = query.strip().lower()
        if q:
            filtered = [
                m
                for m in filtered
                if q in m.name.lower()
                or q in m.league.lower()
                or q in m.home_team.lower()
                or q in m.away_team.lower()
                or any(q in b.lower() for b in m.broadcasts)
            ]
    return filtered


def export_json(matches: list[MatchInfo], output_path: str | Path) -> Path:
    """Write matches to a UTF-8 JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [m.to_dict() for m in matches]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_csv(matches: list[MatchInfo], output_path: str | Path) -> Path:
    """Write matches to a UTF-8 BOM CSV file (Excel-friendly)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "status",
        "status_detail",
        "league",
        "name",
        "score",
        "start_time",
        "broadcasts",
        "links",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in matches:
            writer.writerow(
                {
                    "id": m.id,
                    "status": m.status,
                    "status_detail": m.status_detail,
                    "league": m.league,
                    "name": m.name,
                    "score": m.score,
                    "start_time": m.start_time,
                    "broadcasts": ", ".join(m.broadcasts),
                    "links": " | ".join(item["url"] for item in m.links),
                }
            )
    return path
