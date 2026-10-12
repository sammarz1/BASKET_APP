"""NBA comprehensive game summary extractor (Boxscore, Play-by-Play, and Game Info)."""

import json
from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest

ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
)
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)


class NbaGameSummaryExtractor(BaseExtractor):
    """Fetches full game summaries (boxscore, play-by-play, officials, odds) from ESPN.

    Discovers game IDs from:
    1. An explicit list of `game_ids` (if provided).
    2. Date range (`start` to `end`), loading or fetching scoreboards per day.
    3. Already stored scoreboards in Bronze under `nba/espn_scoreboard/season={season}/`.
    """

    league = "nba"
    endpoint = "summary"

    def __init__(
        self,
        season: str,
        *,
        storage,
        client=None,
        overwrite=False,
        start=None,
        end=None,
        limit=None,
        game_ids: Optional[list[str]] = None,
    ):
        super().__init__(
            season,
            storage=storage,
            client=client,
            overwrite=overwrite,
            start=start,
            end=end,
            limit=limit,
        )
        self.game_ids = game_ids

    def discover_game_ids(self) -> list[str]:
        """Discover game IDs from explicit list, date range, or stored scoreboards."""
        if self.game_ids:
            return self.game_ids

        ids: list[str] = []

        # Case 1: Date range provided
        if self.start is not None and self.end is not None:
            for day in self.iter_dates():
                scoreboard_key = f"nba/espn_scoreboard/season={self.season}/date={day.isoformat()}/scoreboard.json.gz"
                if self.storage.object_exists(scoreboard_key):
                    data = self.storage.get_raw_json(scoreboard_key)
                else:
                    res = self.client.get(
                        ESPN_SCOREBOARD_URL,
                        params={"dates": day.strftime("%Y%m%d"), "limit": 100},
                    )
                    data = json.loads(res.content.decode("utf-8"))

                for event in data.get("events", []):
                    event_id = str(event.get("id", ""))
                    if event_id and event_id not in ids:
                        ids.append(event_id)
            return ids

        # Case 2: Scan stored scoreboards in Bronze
        prefix = f"nba/espn_scoreboard/season={self.season}/"
        keys = self.storage.list_keys(prefix)
        for key in keys:
            if key.endswith("scoreboard.json.gz") or key.endswith("scoreboard.json"):
                data = self.storage.get_raw_json(key)
                for event in data.get("events", []):
                    event_id = str(event.get("id", ""))
                    if event_id and event_id not in ids:
                        ids.append(event_id)

        return ids

    def iter_requests(self) -> Iterable[ExtractRequest]:
        game_ids = self.discover_game_ids()
        for gid in game_ids:
            yield ExtractRequest(
                url=ESPN_SUMMARY_URL,
                params={"event": gid},
                key=self.build_key(f"game_id={gid}", name="summary"),
                metadata={"season": self.season, "game_id": gid},
            )
