from datetime import date

import pytest

from pipeline.dateparse import parse


def check(raw, precision, start, end):
    p = parse(raw)
    assert (p.precision, p.date, p.end) == (precision, start, end), raw
    assert p.raw == (raw or "")


@pytest.mark.parametrize("raw", [
    "Oct 21, 2026",      # Steam US
    "October 21, 2026",
    "Oct 21 2026",
    "21 Oct, 2026",      # Steam UK and many other regions
    "21 Oct 2026",
    "21 October 2026",
    "21. Okt. 2026",     # German
    "21 oct. 2026",      # French / Spanish
    "21 de octubre de 2026",
    "2026-10-21",
    "2026/10/21",
    "21.10.2026",
    "2026年10月21日",    # Chinese / Japanese
    "2026년 10월 21일",  # Korean
    "  oct 21, 2026 ",
])
def test_day(raw):
    check(raw, "day", date(2026, 10, 21), date(2026, 10, 21))


@pytest.mark.parametrize("raw", [
    "October 2026",
    "Oct 2026",
    "Oct. 2026",
    "October, 2026",
    "2026-10",
    "octobre 2026",
    "Oktober 2026",
    "2026年10月",
    "2026년 10월",
])
def test_month(raw):
    check(raw, "month", date(2026, 10, 1), date(2026, 10, 31))


def test_month_end_february_leap_year():
    check("February 2028", "month", date(2028, 2, 1), date(2028, 2, 29))


@pytest.mark.parametrize("raw", [
    "Q4 2026", "Q4, 2026", "2026 Q4", "Q4/2026", "4Q 2026", "q4 2026",
    "Fourth quarter 2026", "2026年第四季度", "2026年 第4四半期",
])
def test_quarter(raw):
    check(raw, "quarter", date(2026, 10, 1), date(2026, 12, 31))


def test_quarter_one():
    check("Q1 2027", "quarter", date(2027, 1, 1), date(2027, 3, 31))


@pytest.mark.parametrize("raw, start, end", [
    ("Spring 2027", date(2027, 3, 1), date(2027, 5, 31)),
    ("Summer 2027", date(2027, 6, 1), date(2027, 8, 31)),
    ("Fall 2027", date(2027, 9, 1), date(2027, 11, 30)),
    ("Autumn 2027", date(2027, 9, 1), date(2027, 11, 30)),
])
def test_season_maps_to_three_month_range(raw, start, end):
    check(raw, "quarter", start, end)


@pytest.mark.parametrize("raw", [
    "2026", "Coming 2026", "Early 2026", "Late 2026", "H1 2026", "Winter 2026", "2026年",
])
def test_year(raw):
    check(raw, "year", date(2026, 1, 1), date(2026, 12, 31))


@pytest.mark.parametrize("raw", [
    None, "", "Coming soon", "To be announced", "TBA", "TBD", "When it's done",
    "Feb 30, 2026",  # not a real day
    "05/06/2026",    # day/month order is ambiguous
    "Q5 2026",
])
def test_unknown(raw):
    check(raw, "unknown", None, None)


@pytest.mark.parametrize("raw, expected", [
    ("13/05/2026", date(2026, 5, 13)),  # first part > 12, so day first
    ("05/13/2026", date(2026, 5, 13)),  # second part > 12, so month first
])
def test_numeric_slash_resolved_when_unambiguous(raw, expected):
    check(raw, "day", expected, expected)


def test_to_dict_uses_iso_strings():
    assert parse("Q4 2026").to_dict() == {
        "raw": "Q4 2026", "precision": "quarter", "date": "2026-10-01", "end": "2026-12-31",
    }
    assert parse("TBA").to_dict() == {"raw": "TBA", "precision": "unknown", "date": None, "end": None}
