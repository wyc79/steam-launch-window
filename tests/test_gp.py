import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline import gp
from pipeline.http import HTTPStatusError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


class FakeClient:
    """Serves scripted replies in order; an Exception in the script is raised."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.mark.parametrize("raw, expected", [
    ("2026-10-11T09:20:38.782", utc(2026, 10, 11, 9, 20, 38, 782000)),
    ("2026-10-08T09:05:56.59", utc(2026, 10, 8, 9, 5, 56, 590000)),
    ("2024-12-09T08:07:07", utc(2024, 12, 9, 8, 7, 7)),
    ("2026-01-09T08:00:30.0800000", utc(2026, 1, 9, 8, 0, 30, 80000)),  # 7 digits, seen in cursors
])
def test_parse_time_is_utc_with_any_fraction(raw, expected):
    assert gp.parse_time(raw) == expected


def test_history_reads_points_newest_first_and_passes_the_key():
    client = FakeClient(fixture("gp_followers_critical_shift.json"))
    res = gp.history(client, "followers", 3395320, "KEY")
    assert res.status == "ok" and res.requests == 1
    assert res.points[0] == (utc(2026, 10, 11, 13, 22, 15, 495000), 4552)
    assert res.points[-1] == (utc(2025, 5, 22, 8, 28, 4, 281000), 257)
    url, params = client.calls[0]
    assert url.endswith("/game/followers/3395320") and params == {"apiKey": "KEY"}


def test_history_keeps_only_points_newer_than_since():
    client = FakeClient(fixture("gp_followers_critical_shift.json"))
    res = gp.history(client, "followers", 3395320, "KEY", since=utc(2026, 10, 8, 11, 52, 45, 401000))
    assert [v for _, v in res.points] == [4552, 4538]


def test_history_follows_the_cursor_until_since_is_reached():
    page1 = fixture("gp_followers_light_no_fire_page1.json")
    page2 = {"steamId": "2719590", "history": [{"followers": 214012, "added": "2026-01-09T08:00:30.08"},
                                                {"followers": 213900, "added": "2026-01-08T08:00:00"}],
             "nextCursor": "2026-01-07T08:00:00.0000000"}
    client = FakeClient(page1, page2)
    res = gp.history(client, "followers", 2719590, "KEY", since=utc(2026, 1, 8, 12))
    assert res.requests == 2  # page 2 reached `since`, so no page 3
    assert client.calls[1][1] == {"apiKey": "KEY", "cursor": "2026-01-09T08:00:30.0800000"}
    assert [v for _, v in res.points] == [248753, 248746, 248746, 214012]


def test_history_stops_at_max_pages():
    page = fixture("gp_followers_light_no_fire_page1.json")
    client = FakeClient(page, page, page)
    res = gp.history(client, "followers", 2719590, "KEY", max_pages=2)
    assert res.requests == 2 and res.complete is False


def test_empty_history_is_null():
    client = FakeClient({"steamId": "5354560", "history": [], "nextCursor": None})
    res = gp.history(client, "followers", 5354560, "KEY")
    assert (res.status, res.points, res.requests) == ("null", [], 1)


def test_points_without_a_value_are_skipped():
    client = FakeClient({"steamId": "1", "history": [{"followers": None, "added": "2026-10-01T00:00:00"},
                                                      {"followers": 3, "added": "2026-09-30T00:00:00"}],
                         "nextCursor": None})
    assert gp.history(client, "followers", 1, "KEY").points == [(utc(2026, 9, 30), 3)]


def test_404_means_not_in_dataset():
    client = FakeClient(HTTPStatusError(404, "https://games-popularity.com/x"))
    res = gp.history(client, "followers", 999999990, "KEY")
    assert (res.status, res.requests) == ("not_in_dataset", 1)


def test_other_errors_propagate():
    client = FakeClient(HTTPStatusError(500, "https://games-popularity.com/x"))
    with pytest.raises(HTTPStatusError):
        gp.history(client, "followers", 1, "KEY")


def test_players_history_uses_the_players_field():
    client = FakeClient({"steamId": "2379780", "history": [{"players": 7638, "added": "2026-10-11T23:00:05.549"}],
                         "nextCursor": None})
    res = gp.history(client, "players", 2379780, "KEY")
    assert client.calls[0][0].endswith("/game/players/2379780") and res.points[0][1] == 7638


def test_value_at_interpolates_between_the_points_around_a_time():
    points = [(utc(2026, 10, 11, 12), 200), (utc(2026, 10, 10, 12), 100)]  # newest first
    assert gp.value_at(points, utc(2026, 10, 11, 0)) == (150, 24.0)  # value, hours between the two points
    assert gp.value_at(points, utc(2026, 10, 12, 0)) is None          # after the newest point
    assert gp.value_at([], utc(2026, 10, 11)) is None


def test_a_404_on_a_later_page_keeps_the_pages_already_fetched():
    client = FakeClient(fixture("gp_followers_light_no_fire_page1.json"), HTTPStatusError(404, "u"))
    res = gp.history(client, "followers", 2719590, "KEY")
    assert len(res.points) == 3 and res.complete is False and res.requests == 2
