"""NBA player profile and career overview extractor."""

from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest

ESPN_ATHLETE_URL = "https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}"


class NbaPlayerExtractor(BaseExtractor):
    """Fetches detailed player biography, career splits, draft info, and contracts.

    Discovers player IDs from stored rosters in Bronze (nba/roster/season={season}/)
    or takes an explicit list of `player_ids`.
    """

    league = "nba"
    endpoint = "player"

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
        player_ids: Optional[list[str]] = None,
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
        self.player_ids = player_ids

    def discover_player_ids(self) -> list[str]:
        """Discover player IDs from explicit list or stored rosters in Bronze."""
        if self.player_ids:
            return self.player_ids

        ids: list[str] = []
        prefix = f"nba/roster/season={self.season}/"
        keys = self.storage.list_keys(prefix)
        for key in keys:
            if key.endswith("roster.json.gz") or key.endswith("roster.json"):
                data = self.storage.get_raw_json(key)
                for athlete in data.get("athletes", []):
                    aid = str(athlete.get("id", ""))
                    if aid and aid not in ids:
                        ids.append(aid)

        return ids

    def iter_requests(self) -> Iterable[ExtractRequest]:
        pids = self.discover_player_ids()
        for pid in pids:
            yield ExtractRequest(
                url=ESPN_ATHLETE_URL.format(athlete_id=pid),
                key=f"nba/player/player_id={pid}/profile.json",
                metadata={"season": self.season, "player_id": pid},
            )
