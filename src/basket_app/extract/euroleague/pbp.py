"""EuroLeague game play-by-play extractor."""

from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest
from basket_app.extract.euroleague.discovery import discover_euroleague_game_codes

PBP_BASE = "https://live.euroleague.net/api/PlayByPlay"


class EuroleaguePbpExtractor(BaseExtractor):
    """Fetches play-by-play event streams for EuroLeague games.

    Discovers game codes automatically from the season games list.
    """

    league = "euroleague"
    endpoint = "playbyplay"

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

    def iter_requests(self) -> Iterable[ExtractRequest]:
        codes = discover_euroleague_game_codes(
            self.storage, self.client, self.season, self.game_codes
        )
        for code in codes:
            yield ExtractRequest(
                url=f"{PBP_BASE}?gamecode={code}&seasoncode={self.season}",
                key=self.build_key(f"game_code={code}", name="playbyplay"),
                metadata={"season": self.season, "game_code": str(code)},
            )
