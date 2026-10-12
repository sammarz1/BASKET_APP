"""NBA team roster and coaching staff extractor."""

import json
from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"


def parse_nba_season_year(season: str) -> int:
    """Parse season string (e.g. '2024-25' -> 2025, '2024' -> 2024)."""
    season = season.strip()
    if "-" in season:
        return int(season.split("-")[0]) + 1
    return int(season)


class NbaRosterExtractor(BaseExtractor):
    """Fetches full player rosters and coaches for NBA teams.

    Discovers team IDs from Bronze storage (nba/teams/season={season}/teams.json.gz)
    or by fetching the ESPN teams list dynamically.
    """

    league = "nba"
    endpoint = "roster"

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
        team_ids: Optional[list[str]] = None,
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
        self.team_ids = team_ids

    def discover_team_ids(self) -> list[str]:
        """Discover 30 NBA team IDs from Bronze storage or ESPN API."""
        if self.team_ids:
            return self.team_ids

        teams_key = f"nba/teams/season={self.season}/teams.json.gz"
        if self.storage.object_exists(teams_key):
            raw_data = self.storage.get_raw_json(teams_key)
        else:
            res = self.client.get(ESPN_TEAMS_URL)
            raw_data = json.loads(res.content.decode("utf-8"))

        tids: list[str] = []
        for sport in raw_data.get("sports", []):
            for league in sport.get("leagues", []):
                for item in league.get("teams", []):
                    team = item.get("team", {})
                    tid = str(team.get("id", ""))
                    if tid and tid not in tids:
                        tids.append(tid)

        return tids or [str(i) for i in range(1, 31)]

    def iter_requests(self) -> Iterable[ExtractRequest]:
        team_ids = self.discover_team_ids()

        for tid in team_ids:
            yield ExtractRequest(
                url=ESPN_ROSTER_URL.format(team_id=tid),
                key=self.build_key(f"team_id={tid}", name="roster"),
                metadata={"season": self.season, "team_id": tid},
            )
