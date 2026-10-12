"""EuroLeague competition clubs/teams extractor."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

API_BASE = "https://api-live.euroleague.net/v2"


class EuroleagueClubsExtractor(BaseExtractor):
    """Fetches all clubs participating in a EuroLeague/EuroCup season."""

    league = "euroleague"
    endpoint = "clubs"

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def iter_requests(self) -> Iterable[ExtractRequest]:
        yield ExtractRequest(
            url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/clubs",
            key=self.build_key(name="clubs"),
            metadata={"season": self.season},
        )
