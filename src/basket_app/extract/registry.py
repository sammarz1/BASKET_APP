"""Maps (league, endpoint) CLI names to extractor classes."""

from basket_app.extract.base import BaseExtractor
from basket_app.extract.euroleague.games import EuroleagueGamesExtractor
from basket_app.extract.nba.espn_scoreboard import NbaEspnScoreboardExtractor
from basket_app.extract.nba.schedule import NbaScheduleExtractor

EXTRACTORS: dict[tuple[str, str], type[BaseExtractor]] = {
    ("nba", "schedule"): NbaScheduleExtractor,
    ("nba", "espn_scoreboard"): NbaEspnScoreboardExtractor,
    ("euroleague", "games"): EuroleagueGamesExtractor,
}


def get_extractor_class(league: str, endpoint: str) -> type[BaseExtractor]:
    try:
        return EXTRACTORS[(league, endpoint)]
    except KeyError:
        available = ", ".join(f"{l}/{e}" for l, e in sorted(EXTRACTORS))
        raise SystemExit(
            f"Unknown extractor '{league}/{endpoint}'. Available: {available}"
        )
