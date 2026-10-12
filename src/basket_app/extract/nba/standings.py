"""NBA standings extractor."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest
from basket_app.extract.nba.roster import parse_nba_season_year

ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"


class NbaStandingsExtractor(BaseExtractor):
    """Fetches full NBA conference and division standings for a season."""

    league = "nba"
    endpoint = "standings"

    def iter_requests(self) -> Iterable[ExtractRequest]:
        year = parse_nba_season_year(self.season)
        yield ExtractRequest(
            url=ESPN_STANDINGS_URL,
            params={"season": year},
            key=self.build_key(name="standings"),
            metadata={"season": self.season, "year": str(year)},
        )
