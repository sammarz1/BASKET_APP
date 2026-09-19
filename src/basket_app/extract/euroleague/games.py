"""EuroLeague games list from the official v2 API (no auth required)."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

API_BASE = "https://api-live.euroleague.net/v2"


class EuroleagueGamesExtractor(BaseExtractor):
    """
    All games for a season. ``season`` is the EuroLeague season code, e.g.
    ``E2025`` (EuroLeague 2025-26) or ``U2025`` (EuroCup); its first character
    is the competition.
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
