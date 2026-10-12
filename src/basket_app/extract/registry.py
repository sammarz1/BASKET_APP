"""Extractor registry mapping (league, endpoint) to extractor classes."""

from typing import Type

from basket_app.extract.base import BaseExtractor
from basket_app.extract.euroleague.boxscore import EuroleagueBoxscoreExtractor
from basket_app.extract.euroleague.clubs import EuroleagueClubsExtractor
from basket_app.extract.euroleague.games import EuroleagueGamesExtractor
from basket_app.extract.euroleague.pbp import EuroleaguePbpExtractor
from basket_app.extract.euroleague.people import EuroleaguePeopleExtractor
from basket_app.extract.euroleague.roster import EuroleagueRosterExtractor
from basket_app.extract.euroleague.shots import EuroleagueShotsExtractor
from basket_app.extract.euroleague.standings import EuroleagueStandingsExtractor
from basket_app.extract.nba.espn_scoreboard import NbaEspnScoreboardExtractor
from basket_app.extract.nba.game_summary import NbaGameSummaryExtractor
from basket_app.extract.nba.player import NbaPlayerExtractor
from basket_app.extract.nba.roster import NbaRosterExtractor
from basket_app.extract.nba.schedule import NbaScheduleExtractor
from basket_app.extract.nba.standings import NbaStandingsExtractor
from basket_app.extract.nba.teams import NbaTeamsExtractor

EXTRACTORS: dict[tuple[str, str], type[BaseExtractor]] = {
    # NBA
    ("nba", "schedule"): NbaScheduleExtractor,
    ("nba", "scoreboard"): NbaEspnScoreboardExtractor,
    ("nba", "espn_scoreboard"): NbaEspnScoreboardExtractor,
    ("nba", "summary"): NbaGameSummaryExtractor,
    ("nba", "game_summary"): NbaGameSummaryExtractor,
    ("nba", "boxscore"): NbaGameSummaryExtractor,
    ("nba", "teams"): NbaTeamsExtractor,
    ("nba", "roster"): NbaRosterExtractor,
    ("nba", "standings"): NbaStandingsExtractor,
    ("nba", "player"): NbaPlayerExtractor,
    ("nba", "athlete"): NbaPlayerExtractor,
    # EuroLeague
    ("euroleague", "games"): EuroleagueGamesExtractor,
    ("euroleague", "clubs"): EuroleagueClubsExtractor,
    ("euroleague", "teams"): EuroleagueClubsExtractor,
    ("euroleague", "roster"): EuroleagueRosterExtractor,
    ("euroleague", "boxscore"): EuroleagueBoxscoreExtractor,
    ("euroleague", "stats"): EuroleagueBoxscoreExtractor,
    ("euroleague", "pbp"): EuroleaguePbpExtractor,
    ("euroleague", "playbyplay"): EuroleaguePbpExtractor,
    ("euroleague", "shots"): EuroleagueShotsExtractor,
    ("euroleague", "points"): EuroleagueShotsExtractor,
    ("euroleague", "standings"): EuroleagueStandingsExtractor,
    ("euroleague", "people"): EuroleaguePeopleExtractor,
    ("euroleague", "players"): EuroleaguePeopleExtractor,
}


def get_extractor_class(league: str, endpoint: str) -> type[BaseExtractor]:
    """Retrieve an extractor class by league and endpoint."""
    key = (league.lower().strip(), endpoint.lower().strip())
    if key in EXTRACTORS:
        return EXTRACTORS[key]
    available = ", ".join(f"{l}/{e}" for l, e in sorted(EXTRACTORS))
    raise ValueError(f"Unknown extractor '{league}/{endpoint}'. Available: {available}")


def list_available_extractors() -> list[str]:
    """Return formatted list of all registered extractors."""
    return [f"{l}/{e}" for l, e in sorted(EXTRACTORS)]
