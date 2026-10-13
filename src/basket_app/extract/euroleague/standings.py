"""EuroLeague standings extractor."""

import json
from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest

API_BASE = "https://api-live.euroleague.net/v2"


class EuroleagueStandingsExtractor(BaseExtractor):
    """Fetches regular season standings for EuroLeague."""

    league = "euroleague"
    endpoint = "standings"

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
        round_number: Optional[int] = None,
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
        self.round_number = round_number

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def discover_latest_round(self) -> int:
        """Find the maximum played regular season round for the season."""
        if self.round_number:
            return self.round_number

        # 1. Check games calendar in Bronze storage to find latest played RS round
        games_key = f"euroleague/games/season={self.season}/games.json.gz"
        if self.storage.object_exists(games_key):
            try:
                raw_games = self.storage.get_raw_json(games_key)
                g_list = (
                    raw_games.get("data", [])
                    if isinstance(raw_games, dict)
                    else raw_games
                )
                played_rs: list[int] = []
                for g in g_list:
                    if not g.get("played", False):
                        continue
                    pt = g.get("phaseType")
                    p_code = pt.get("code") if isinstance(pt, dict) else pt
                    if p_code == "RS" and "round" in g:
                        played_rs.append(g["round"])
                if played_rs:
                    return max(played_rs)
            except Exception:
                pass

        # 2. Fallback to querying rounds list from API
        try:
            url = f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/rounds"
            res = self.client.get(url)
            data = json.loads(res.content.decode("utf-8"))
            rounds = data.get("data", [])
            rs_rounds = [r["round"] for r in rounds if r.get("phaseTypeCode") == "RS"]
            if rs_rounds:
                return max(rs_rounds)
        except Exception:
            pass
        return 34

    def iter_requests(self) -> Iterable[ExtractRequest]:
        rnd = self.discover_latest_round()
        yield ExtractRequest(
            url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/rounds/{rnd}/standings",
            key=self.build_key(name="standings"),
            metadata={"season": self.season, "round": str(rnd)},
        )
