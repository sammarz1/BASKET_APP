"""EuroLeague club roster and personnel extractor."""

from typing import Iterable, Optional

from basket_app.extract.base import BaseExtractor, ExtractRequest
from basket_app.extract.euroleague.discovery import (
    API_BASE,
    discover_euroleague_club_codes,
)


class EuroleagueRosterExtractor(BaseExtractor):
    """Fetches team rosters and coaching staff for EuroLeague clubs.

    Discovers club codes from the season clubs list.
    """

    league = "euroleague"
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
        club_codes: Optional[list[str]] = None,
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
        self.club_codes = club_codes

    @property
    def competition(self) -> str:
        return self.season[0].upper()

    def iter_requests(self) -> Iterable[ExtractRequest]:
        codes = discover_euroleague_club_codes(
            self.storage, self.client, self.season, self.club_codes
        )
        for code in codes:
            yield ExtractRequest(
                url=f"{API_BASE}/competitions/{self.competition}/seasons/{self.season}/clubs/{code}/people",
                key=self.build_key(f"club_code={code}", name="roster"),
                metadata={"season": self.season, "club_code": str(code)},
            )
