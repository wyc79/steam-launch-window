"""Parse fuzzy Steam release date strings.

parse("Q3 2026") -> ParsedDate(raw="Q3 2026", precision="quarter",
                               date=2026-07-01, end=2026-09-30)

`date` is the first day the game could launch and `end` is the last.
They are equal for day precision and None for unknown.

Precision is one of day, month, quarter, year, unknown. Two looser forms
are folded in so ranges stay honest:
- Seasons (spring, summer, fall/autumn) become "quarter" with that
  season's three months. Winter is ambiguous across years, so it is "year".
- "Early 2026", "H1 2026" and similar become "year".
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

DAY, MONTH, QUARTER, YEAR, UNKNOWN = "day", "month", "quarter", "year", "unknown"

# Month names and abbreviations after lowercasing and stripping accents and dots.
_MONTHS = {
    1: "january jan januar janvier enero ene janeiro gennaio gen",
    2: "february feb februar fevrier fev febrero febr fevereiro fevr febbraio",
    3: "march mar marz maerz mrz mars marzo marco",
    4: "april apr avril avr abril abr aprile",
    5: "may mai mayo maio maggio mag",
    6: "june jun juni juin junio junho giugno giu",
    7: "july jul juli juillet juil julio julho luglio lug",
    8: "august aug aout agosto ago",
    9: "september sep sept septembre septiembre setembro settembre set",
    10: "october oct oktober okt octobre octubre outubro out ottobre ott",
    11: "november nov novembre noviembre novembro",
    12: "december dec dezember dez decembre diciembre dic dezembro dicembre",
}
_MONTH_BY_NAME = {name: num for num, names in _MONTHS.items() for name in names.split()}
_MONTH_RE = "|".join(sorted(_MONTH_BY_NAME, key=len, reverse=True))

_QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_CJK_QUARTER_NUMS = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4}
_SEASON_START = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9}

_Y = r"(?P<y>(?:19|20)\d\d)"
_M = rf"(?P<mon>{_MONTH_RE})"
_D = r"(?P<d>\d{1,2})"

# Ordered from most to least specific; the first match wins.
_DAY_PATTERNS = [
    re.compile(rf"\b{_M}\s+{_D}(?:st|nd|rd|th)?\s*,?\s*{_Y}\b"),           # oct 21, 2026
    re.compile(rf"\b{_D}\s*(?:de\s+)?{_M}\s*,?\s*(?:de\s+)?{_Y}\b"),      # 21 oct, 2026 / 21 de octubre de 2026
    re.compile(rf"\b{_Y}[-/](?P<m>\d{{1,2}})[-/]{_D}\b"),                  # 2026-10-21
    re.compile(rf"\b{_D}\.(?P<m>\d{{1,2}})\.{_Y}\b"),                       # 21.10.2026
    re.compile(rf"{_Y}\s*[年년]\s*(?P<m>\d{{1,2}})\s*[月월]\s*{_D}\s*[日일]"),  # 2026年10月21日
]
_SLASH_DAY = re.compile(rf"\b(?P<a>\d{{1,2}})/(?P<b>\d{{1,2}})/{_Y}\b")
_MONTH_PATTERNS = [
    re.compile(rf"\b{_M}\s*,?\s*(?:de\s+)?{_Y}\b"),          # october 2026
    re.compile(rf"\b{_Y}-(?P<m>\d{{1,2}})\b(?!-)"),         # 2026-10
    re.compile(rf"{_Y}\s*[年년]\s*(?P<m>\d{{1,2}})\s*[月월]"),  # 2026年10月
]
_QUARTER_PATTERNS = [
    re.compile(rf"\bq(?P<q>\d)\s*[,/]?\s*{_Y}\b"),           # q4 2026
    re.compile(rf"\b{_Y}\s*[,/]?\s*q(?P<q>\d)\b"),           # 2026 q4
    re.compile(rf"\b(?P<q>\d)q\s*{_Y}\b"),                    # 4q 2026
    re.compile(rf"\b(?P<qw>first|second|third|fourth)\s+quarter\s*(?:of\s+)?{_Y}\b"),
    re.compile(rf"{_Y}\s*年?\s*第\s*(?P<qc>[一二三四1-4])\s*(?:季度|四半期)"),
]
_SEASON = re.compile(rf"\b(?P<s>spring|summer|fall|autumn)\s*(?:of\s+)?{_Y}\b")
_YEAR = re.compile(rf"(?:^|\D){_Y}(?:$|\D)")


@dataclass(frozen=True)
class ParsedDate:
    raw: str
    precision: str
    date: date | None
    end: date | None

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "precision": self.precision,
            "date": self.date.isoformat() if self.date else None,
            "end": self.end.isoformat() if self.end else None,
        }


def _normalize(raw: str) -> str:
    # Strip accents (fevrier, aout), then recompose so Korean syllables survive.
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = unicodedata.normalize("NFC", text).lower()
    # Drop abbreviation dots ("Okt.") but keep dots between digits ("21.10.2026").
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _span(y: int, first_month: int, months: int) -> tuple[date, date]:
    last = first_month + months - 1
    return date(y, first_month, 1), _month_end(y + (last - 1) // 12, (last - 1) % 12 + 1)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _month_num(g: re.Match) -> int:
    if g.groupdict().get("mon"):
        return _MONTH_BY_NAME[g["mon"]]
    return int(g["m"])


def parse(raw: str | None) -> ParsedDate:
    raw = raw or ""
    unknown = ParsedDate(raw, UNKNOWN, None, None)
    text = _normalize(raw)
    if not text:
        return unknown

    for pat in _DAY_PATTERNS:
        if g := pat.search(text):
            d = _safe_date(int(g["y"]), _month_num(g), int(g["d"]))
            return ParsedDate(raw, DAY, d, d) if d else unknown

    if g := _SLASH_DAY.search(text):
        a, b, y = int(g["a"]), int(g["b"]), int(g["y"])
        if a > 12 >= b:
            d = _safe_date(y, b, a)
        elif b > 12 >= a:
            d = _safe_date(y, a, b)
        else:
            d = None  # 05/06/2026 could be May 6 or June 5
        return ParsedDate(raw, DAY, d, d) if d else unknown

    for pat in _MONTH_PATTERNS:
        if g := pat.search(text):
            y, m = int(g["y"]), _month_num(g)
            if not 1 <= m <= 12:
                return unknown
            return ParsedDate(raw, MONTH, date(y, m, 1), _month_end(y, m))

    for pat in _QUARTER_PATTERNS:
        if g := pat.search(text):
            gd = g.groupdict()
            if gd.get("qw"):
                q = _QUARTER_WORDS[gd["qw"]]
            elif gd.get("qc"):
                q = _CJK_QUARTER_NUMS[gd["qc"]]
            else:
                q = int(gd["q"])
            if not 1 <= q <= 4:
                return unknown
            start, end = _span(int(g["y"]), 3 * q - 2, 3)
            return ParsedDate(raw, QUARTER, start, end)

    if g := _SEASON.search(text):
        start, end = _span(int(g["y"]), _SEASON_START[g["s"]], 3)
        return ParsedDate(raw, QUARTER, start, end)

    if g := _YEAR.search(text):
        y = int(g["y"])
        return ParsedDate(raw, YEAR, date(y, 1, 1), date(y, 12, 31))

    return unknown
