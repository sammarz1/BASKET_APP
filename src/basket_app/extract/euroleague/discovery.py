"""EuroLeague discovery utilities."""

import json
from typing import Optional

from basket_app.core.http import HttpClient
from basket_app.core.storage import BronzeStorage

API_BASE = "https://api-live.euroleague.net/v2"


def discover_euroleague_game_codes(
    storage: BronzeStorage,
    client: HttpClient,
    season: str,
    game_codes: Optional[list[int]] = None,
) -> list[int]:
    """Discover completed game codes for a season from Bronze storage or API."""
    if game_codes:
        return sorted(game_codes)

    calendar_key = f"euroleague/games/season={season}/games.json.gz"
    if storage.object_exists(calendar_key):
        raw_calendar = storage.get_raw_json(calendar_key)
    else:
        competition = season[0].upper()
        url = f"{API_BASE}/competitions/{competition}/seasons/{season}/games"
        res = client.get(url)
        raw_calendar = json.loads(res.content.decode("utf-8"))

    games_list = (
        raw_calendar.get("data", []) if isinstance(raw_calendar, dict) else raw_calendar
    )
    codes = [
        g["gameCode"] for g in games_list if g.get("played", True) and "gameCode" in g
    ]
    return sorted(codes)


def discover_euroleague_club_codes(
    storage: BronzeStorage,
    client: HttpClient,
    season: str,
    club_codes: Optional[list[str]] = None,
) -> list[str]:
    """Discover club codes for a season from Bronze storage or API."""
    if club_codes:
        return sorted(club_codes)

    clubs_key = f"euroleague/clubs/season={season}/clubs.json.gz"
    if storage.object_exists(clubs_key):
        raw_clubs = storage.get_raw_json(clubs_key)
    else:
        competition = season[0].upper()
        url = f"{API_BASE}/competitions/{competition}/seasons/{season}/clubs"
        res = client.get(url)
        raw_clubs = json.loads(res.content.decode("utf-8"))

    clubs_list = raw_clubs.get("data", []) if isinstance(raw_clubs, dict) else raw_clubs
    codes = [c["code"] for c in clubs_list if "code" in c]
    return sorted(codes)
