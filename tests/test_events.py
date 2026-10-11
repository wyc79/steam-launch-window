"""Checks on data/events.yaml and its loader."""

from datetime import date, datetime

import pytest

from pipeline import events as ev


def sale(**kw):
    return {"name": "Steam Summer Sale 2026", "type": "seasonal_sale", "start": date(2026, 6, 25),
            "end": date(2026, 7, 9), "confidence": "high", "source": "https://example.com", **kw}


def release(**kw):
    return {"name": "Some Game", "type": "major_release", "start": date(2026, 3, 5), "end": date(2026, 3, 5),
            "confidence": "high", "source": "https://example.com", "on_steam_at_launch": True,
            "release_kind": "full", "steam_appid": 123, **kw}


# -- the real file -----------------------------------------------------------

def test_events_file_is_valid():
    assert ev.validate(ev.load()) == []


def test_events_file_is_plain_ascii():
    ev.PATH.read_bytes().decode("ascii")


# -- window semantics --------------------------------------------------------

def test_steam_events_run_from_10am_to_10am_pacific():
    start, end = ev.window(sale())
    assert start == datetime(2026, 6, 25, 10, tzinfo=ev.PACIFIC)
    assert end == datetime(2026, 7, 9, 10, tzinfo=ev.PACIFIC)


def test_other_events_cover_whole_days():
    start, end = ev.window(release())
    assert start == datetime(2026, 3, 5, 0, tzinfo=ev.PACIFIC)
    assert end == datetime(2026, 3, 6, 0, tzinfo=ev.PACIFIC)


# -- validation catches mistakes ---------------------------------------------

@pytest.mark.parametrize("event, problem", [
    (sale(type="aaa_release"), "unknown type"),
    (sale(start=date(2026, 7, 10)), "start after end"),
    (sale(end=date(2026, 6, 25)), "must end on a later day"),
    (sale(source="http://example.com"), "https link"),
    (sale(confidence="sure"), "confidence"),
    (sale(region="CN"), "not allowed"),
    (release(release_kind="remaster"), "release_kind"),
    (release(on_steam_at_launch="yes"), "on_steam_at_launch"),
    ({k: v for k, v in release().items() if k != "steam_appid"}, "no steam_appid"),
    (release(free_to_play=False), "only when true"),
    (release(surprise="sleeper"), "surprise"),
    (release(end=date(2026, 3, 6)), "single day"),
    ({**sale(type="themed_fest"), "tags": []}, "tags"),
    ({**sale(type="regional_holiday"), "region": "EU"}, "region"),
])
def test_validate_reports(event, problem):
    problems = ev.validate([event])
    assert any(problem in p for p in problems), problems


def test_validate_accepts_good_entries():
    assert ev.validate([release(free_to_play=True, surprise="shadow_drop"), sale()]) == []


def test_validate_reports_duplicates_and_order():
    assert any("duplicate" in p for p in ev.validate([sale(), sale()]))
    later = sale(name="Steam Autumn Sale 2026", start=date(2026, 10, 1), end=date(2026, 10, 8))
    assert any("not sorted" in p for p in ev.validate([later, sale()]))


def test_check_against_steam(tmp_path):
    from pipeline import storage

    storage.write_csv(tmp_path / "history" / "games.csv", [
        {"appid": 123, "launch_date": "2026-03-04", "steam_release_ts": ""},
        {"appid": 456, "launch_date": "2024-05-06", "steam_release_ts": 1758819600},  # left EA 2025-09-25
    ], ["appid", "launch_date", "steam_release_ts"])
    exit_ = release(name="Other 1.0", steam_appid=456, release_kind="early_access_exit",
                    start=date(2025, 9, 25), end=date(2025, 9, 25))
    future_exit = release(name="Other 1.0 later", steam_appid=456, release_kind="early_access_exit",
                          start=date(2027, 1, 1), end=date(2027, 1, 1))
    known_wrong = release(name="Black Ops 7", steam_appid=3606480)
    problems = ev.check_against_steam([release(), exit_, future_exit, known_wrong], tmp_path)
    assert problems == ["'Some Game': events.yaml says 2026-03-05, Steam says 2026-03-04 (app 123)"]
