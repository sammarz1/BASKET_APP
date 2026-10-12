"""NBA teams list extractor."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"


class NbaTeamsExtractor(BaseExtractor):
    """Fetches all 30 NBA teams and their basic metadata."""

    league = "nba"
    endpoint = "teams"

    def iter_requests(self) -> Iterable[ExtractRequest]:
        yield ExtractRequest(
            url=ESPN_TEAMS_URL,
            key=self.build_key(name="teams"),
            metadata={"season": self.season},
        )
