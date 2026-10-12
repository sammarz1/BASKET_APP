"""EuroLeague games list from the official v2 API."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

API_BASE = "https://api-live.euroleague.net/v2"


class EuroleagueGamesExtractor(BaseExtractor):
    """Fetches all games for a season from the official EuroLeague API.

    Season format: 'E2024' (EuroLeague 2024-25) or 'U2024' (EuroCup).
    The first character denotes the competition.
    """

    league = "euroleague"
    endpoint = "games"

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def iter_requests(self) -> Iterable[ExtractRequest]:
        yield ExtractRequest(
            url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/games",
            key=self.build_key(name="games"),
            metadata={"season": self.season},
        )
