"""NBA league schedule from the public NBA CDN (static JSON, no auth).

NOTE: cdn.nba.com and stats.nba.com are geo-blocked outside the US (Akamai
"Access Denied" / hanging connections). Use a US VPN, or the ESPN extractors.
"""

from typing import Iterable

from basket_app.extract.base import BaseExtractor, ExtractRequest

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


class NbaScheduleExtractor(BaseExtractor):
    """
    Full-season schedule for the current NBA season.

    The CDN only serves the current season; ``season`` is used purely for the
    bronze partition. Re-run with ``--overwrite`` to refresh it.
    """

    league = "nba"
    endpoint = "schedule"
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
    }

    def iter_requests(self) -> Iterable[ExtractRequest]:
        yield ExtractRequest(
            url=SCHEDULE_URL,
            key=self.build_key(name="schedule"),
            metadata={"season": self.season},
        )
