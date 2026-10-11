"""Checks on the hand-maintained data/events.yaml."""

from datetime import date
from pathlib import Path

import pytest
import yaml

PATH = Path(__file__).resolve().parents[1] / "data" / "events.yaml"
TYPES = {"seasonal_sale", "next_fest", "themed_fest", "aaa_release", "regional_holiday"}


@pytest.fixture(scope="module")
def events():
    return yaml.safe_load(PATH.read_text(encoding="ascii"))["events"]


def test_every_event_is_well_formed(events):
    for e in events:
        assert e["type"] in TYPES, e
        assert isinstance(e["start"], date) and isinstance(e["end"], date), e
        assert e["start"] <= e["end"], e
        assert e["source"].startswith("https://"), e
        assert e["confidence"] in {"high", "medium", "low"}, e


def test_types_carry_their_extra_fields(events):
    for e in events:
        if e["type"] == "aaa_release":
            assert isinstance(e["on_steam_at_launch"], bool), e
        if e["type"] == "regional_holiday":
            assert e["region"] in {"CN", "JP", "US", "global"}, e


def test_sorted_and_no_duplicates(events):
    keys = [(e["start"], e["type"], e["name"]) for e in events]
    assert keys == sorted(keys)
    assert len({(e["name"], e["start"]) for e in events}) == len(events)


def test_file_is_plain_ascii():
    PATH.read_bytes().decode("ascii")


def test_known_dates(events):
    by_name = {e["name"]: e for e in events}
    assert by_name["Lunar New Year 2026"]["start"] == date(2026, 2, 16)
    assert by_name["US Thanksgiving to Cyber Monday 2026"]["start"] == date(2026, 11, 26)
