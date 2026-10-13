"""Unit tests for concrete extractors (EuroLeague & NBA)."""

from datetime import date
from unittest.mock import MagicMock

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


def test_euroleague_games_extractor_requests():
    storage = MagicMock()
    extractor = EuroleagueGamesExtractor("E2024", storage=storage)

    requests = list(extractor.iter_requests())
    assert len(requests) == 1
    req = requests[0]

    assert (
        req.url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/games"
    )
    assert req.key == "euroleague/games/season=E2024/games.json"
    assert req.metadata == {"season": "E2024"}


def test_nba_espn_scoreboard_extractor_requests():
    storage = MagicMock()
    extractor = NbaEspnScoreboardExtractor(
        "2024-25",
        storage=storage,
        start=date(2024, 11, 1),
        end=date(2024, 11, 2),
    )

    requests = list(extractor.iter_requests())
    assert len(requests) == 2

    req1, req2 = requests
    assert req1.params == {"dates": "20241101", "limit": 100}
    assert (
        req1.key == "nba/espn_scoreboard/season=2024-25/date=2024-11-01/scoreboard.json"
    )
    assert req1.metadata == {"season": "2024-25", "date": "2024-11-01"}

    assert req2.params == {"dates": "20241102", "limit": 100}
    assert (
        req2.key == "nba/espn_scoreboard/season=2024-25/date=2024-11-02/scoreboard.json"
    )


def test_nba_schedule_extractor_requests():
    storage = MagicMock()
    extractor = NbaScheduleExtractor("2024-25", storage=storage)

    requests = list(extractor.iter_requests())
    assert len(requests) == 1
    req = requests[0]

    assert req.url == "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
    assert req.key == "nba/schedule/season=2024-25/schedule.json"
    assert req.metadata == {"season": "2024-25"}
    assert extractor.default_headers["Origin"] == "https://www.nba.com"


def test_euroleague_boxscore_extractor_auto_discovery():
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.get_raw_json.return_value = {
        "data": [
            {"gameCode": 10, "played": True},
            {"gameCode": 20, "played": False},  # not played yet
            {"gameCode": 30, "played": True},
        ]
    }

    extractor = EuroleagueBoxscoreExtractor("E2024", storage=storage)
    requests = list(extractor.iter_requests())

    assert len(requests) == 2
    assert (
        requests[0].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/games/10/stats"
    )
    assert (
        requests[0].key == "euroleague/boxscore/season=E2024/game_code=10/boxscore.json"
    )
    assert requests[0].metadata == {"season": "E2024", "game_code": "10"}

    assert (
        requests[1].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/games/30/stats"
    )


def test_euroleague_pbp_extractor_requests():
    storage = MagicMock()
    extractor = EuroleaguePbpExtractor("E2024", storage=storage, game_codes=[5])
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://live.euroleague.net/api/PlayByPlay?gamecode=5&seasoncode=E2024"
    )
    assert (
        requests[0].key
        == "euroleague/playbyplay/season=E2024/game_code=5/playbyplay.json"
    )
    assert requests[0].metadata == {"season": "E2024", "game_code": "5"}


def test_euroleague_shots_extractor_requests():
    storage = MagicMock()
    extractor = EuroleagueShotsExtractor("E2024", storage=storage, game_codes=[5])
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://live.euroleague.net/api/Points?gamecode=5&seasoncode=E2024"
    )
    assert requests[0].key == "euroleague/shots/season=E2024/game_code=5/shots.json"
    assert requests[0].metadata == {"season": "E2024", "game_code": "5"}


def test_nba_game_summary_extractor_requests():
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.get_raw_json.return_value = {
        "events": [{"id": "401704698", "name": "BOS @ CHA"}]
    }

    extractor = NbaGameSummaryExtractor(
        "2024-25",
        storage=storage,
        start=date(2024, 11, 1),
        end=date(2024, 11, 1),
    )
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    req = requests[0]
    assert (
        req.url
        == "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
    )
    assert req.params == {"event": "401704698"}
    assert req.key == "nba/summary/season=2024-25/game_id=401704698/summary.json"
    assert req.metadata == {"season": "2024-25", "game_id": "401704698"}


def test_nba_game_summary_filters_uncompleted_games():
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.get_raw_json.return_value = {
        "events": [
            {
                "id": "1001",
                "name": "LAL @ GSW",
                "status": {"type": {"completed": True, "state": "post"}},
            },
            {
                "id": "1002",
                "name": "BOS @ MIA",
                "status": {"type": {"completed": False, "state": "pre"}},
            },
        ]
    }

    extractor = NbaGameSummaryExtractor(
        "2024-25",
        storage=storage,
        start=date(2024, 11, 1),
        end=date(2024, 11, 1),
    )
    requests = list(extractor.iter_requests())
    assert len(requests) == 1
    assert requests[0].params == {"event": "1001"}


def test_euroleague_clubs_extractor_requests():
    storage = MagicMock()
    extractor = EuroleagueClubsExtractor("E2024", storage=storage)
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/clubs"
    )
    assert requests[0].key == "euroleague/clubs/season=E2024/clubs.json"


def test_euroleague_roster_extractor_requests():
    storage = MagicMock()
    extractor = EuroleagueRosterExtractor("E2024", storage=storage, club_codes=["BER"])
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/clubs/BER/people"
    )
    assert requests[0].key == "euroleague/roster/season=E2024/club_code=BER/roster.json"


def test_nba_teams_extractor_requests():
    storage = MagicMock()
    extractor = NbaTeamsExtractor("2024-25", storage=storage)
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    )
    assert requests[0].key == "nba/teams/season=2024-25/teams.json"


def test_nba_roster_extractor_requests():
    storage = MagicMock()
    extractor = NbaRosterExtractor("2024-25", storage=storage, team_ids=["1"])
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/1/roster"
    )
    assert requests[0].params == {}
    assert requests[0].key == "nba/roster/season=2024-25/team_id=1/roster.json"


def test_euroleague_standings_extractor_requests():
    storage = MagicMock()
    extractor = EuroleagueStandingsExtractor("E2024", storage=storage, round_number=34)
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/rounds/34/standings"
    )
    assert requests[0].key == "euroleague/standings/season=E2024/standings.json"


def test_euroleague_standings_auto_discovers_played_round():
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.get_raw_json.return_value = {
        "data": [
            {"round": 10, "played": True, "phaseType": {"code": "RS"}},
            {"round": 11, "played": True, "phaseType": {"code": "RS"}},
            {"round": 12, "played": False, "phaseType": {"code": "RS"}},
        ]
    }

    extractor = EuroleagueStandingsExtractor("E2024", storage=storage)
    requests = list(extractor.iter_requests())
    assert len(requests) == 1
    assert "rounds/11/standings" in requests[0].url


def test_euroleague_people_extractor_requests():
    storage = MagicMock()
    extractor = EuroleaguePeopleExtractor("E2024", storage=storage)
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://api-live.euroleague.net/v2/competitions/E/seasons/E2024/people"
    )
    assert requests[0].params == {"limit": 1000}
    assert requests[0].key == "euroleague/people/season=E2024/people.json"


def test_nba_standings_extractor_requests():
    storage = MagicMock()
    extractor = NbaStandingsExtractor("2024-25", storage=storage)
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    )
    assert requests[0].params == {"season": 2025}
    assert requests[0].key == "nba/standings/season=2024-25/standings.json"


def test_nba_player_extractor_requests():
    storage = MagicMock()
    extractor = NbaPlayerExtractor("2024-25", storage=storage, player_ids=["4278039"])
    requests = list(extractor.iter_requests())

    assert len(requests) == 1
    assert (
        requests[0].url
        == "https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/4278039"
    )
    assert requests[0].key == "nba/player/player_id=4278039/profile.json"
