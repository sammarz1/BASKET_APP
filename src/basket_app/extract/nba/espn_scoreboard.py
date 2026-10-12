"""NBA daily scoreboard from ESPN's public API."""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)


class NbaEspnScoreboardExtractor(BaseExtractor):
    """Daily scoreboard from ESPN, providing game IDs and final scores per date."""

    league = "nba"
    endpoint = "espn_scoreboard"

    def iter_requests(self) -> Iterable[ExtractRequest]:
        for day in self.iter_dates():
            yield ExtractRequest(
                url=SCOREBOARD_URL,
                params={"dates": day.strftime("%Y%m%d"), "limit": 100},
                key=self.build_key(f"date={day.isoformat()}", name="scoreboard"),
                metadata={"season": self.season, "date": day.isoformat()},
            )
