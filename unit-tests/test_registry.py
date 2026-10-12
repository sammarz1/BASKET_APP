"""Unit tests for extractor registry."""

import pytest

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
from basket_app.extract.registry import (
    get_extractor_class,
    list_available_extractors,
)


def test_get_extractor_class_success():
    assert get_extractor_class("nba", "scoreboard") is NbaEspnScoreboardExtractor
    assert get_extractor_class("nba", "summary") is NbaGameSummaryExtractor
    assert get_extractor_class("nba", "boxscore") is NbaGameSummaryExtractor
    assert get_extractor_class("nba", "schedule") is NbaScheduleExtractor
    assert get_extractor_class("nba", "teams") is NbaTeamsExtractor
    assert get_extractor_class("nba", "roster") is NbaRosterExtractor
    assert get_extractor_class("nba", "standings") is NbaStandingsExtractor
    assert get_extractor_class("nba", "player") is NbaPlayerExtractor

    assert get_extractor_class("euroleague", "games") is EuroleagueGamesExtractor
    assert get_extractor_class("euroleague", "clubs") is EuroleagueClubsExtractor
    assert get_extractor_class("euroleague", "roster") is EuroleagueRosterExtractor
    assert get_extractor_class("euroleague", "boxscore") is EuroleagueBoxscoreExtractor
    assert get_extractor_class("euroleague", "pbp") is EuroleaguePbpExtractor
    assert get_extractor_class("euroleague", "shots") is EuroleagueShotsExtractor
    assert (
        get_extractor_class("euroleague", "standings") is EuroleagueStandingsExtractor
    )
    assert get_extractor_class("euroleague", "people") is EuroleaguePeopleExtractor
    assert get_extractor_class("euroleague", "players") is EuroleaguePeopleExtractor


def test_get_extractor_class_case_insensitive():
    assert get_extractor_class("NBA", "SCOREBOARD") is NbaEspnScoreboardExtractor
    assert get_extractor_class("NBA", "STANDINGS") is NbaStandingsExtractor
    assert (
        get_extractor_class("EUROLEAGUE", "STANDINGS") is EuroleagueStandingsExtractor
    )


def test_get_extractor_class_unknown():
    with pytest.raises(ValueError, match="Unknown extractor 'fake/endpoint'"):
        get_extractor_class("fake", "endpoint")


def test_list_available_extractors():
    available = list_available_extractors()
    assert "nba/scoreboard" in available
    assert "nba/summary" in available
    assert "nba/teams" in available
    assert "nba/roster" in available
    assert "nba/standings" in available
    assert "nba/player" in available
    assert "euroleague/games" in available
    assert "euroleague/clubs" in available
    assert "euroleague/roster" in available
    assert "euroleague/boxscore" in available
    assert "euroleague/pbp" in available
    assert "euroleague/shots" in available
    assert "euroleague/standings" in available
    assert "euroleague/people" in available
