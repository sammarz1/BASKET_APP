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
        """Find the maximum regular season round for the season."""
        if self.round_number:
            return self.round_number

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
