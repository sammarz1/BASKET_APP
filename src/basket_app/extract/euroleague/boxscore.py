"""EuroLeague game boxscore extractor."""

from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest
from basket_app.extract.euroleague.discovery import (
    API_BASE,
    discover_euroleague_game_codes,
)


class EuroleagueBoxscoreExtractor(BaseExtractor):
    """Fetches detailed player & team boxscores for EuroLeague games.

    Discovers game codes from the season games list in Bronze storage
    (euroleague/games/season={season}/games.json.gz). If not found in storage,
    it fetches the games list dynamically.
    """

    league = "euroleague"
    endpoint = "boxscore"

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
        game_codes: Optional[list[int]] = None,
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
        self.game_codes = game_codes

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def iter_requests(self) -> Iterable[ExtractRequest]:
        codes = discover_euroleague_game_codes(
            self.storage, self.client, self.season, self.game_codes
        )
        for code in codes:
            yield ExtractRequest(
                url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/games/{code}/stats",
                key=self.build_key(f"game_code={code}", name="boxscore"),
                metadata={"season": self.season, "game_code": str(code)},
            )
