"""NBA daily scoreboard from ESPN's public site API (works outside the US).

One object per date. The scoreboard lists every game that day with ESPN event
ids, which feed the per-game summary/boxscore endpoint later.
"""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)


class NbaEspnScoreboardExtractor(BaseExtractor):
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
