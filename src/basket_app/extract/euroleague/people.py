"""EuroLeague people and players directory extractor."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

API_BASE = "https://api-live.euroleague.net/v2"


class EuroleaguePeopleExtractor(BaseExtractor):
    """Fetches the complete registry of all players, coaches, and staff for a season."""

    league = "euroleague"
    endpoint = "people"

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def iter_requests(self) -> Iterable[ExtractRequest]:
        yield ExtractRequest(
            url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/people",
            params={"limit": 1000},
            key=self.build_key(name="people"),
            metadata={"season": self.season},
        )
