"""Wrapper for the Games Popularity API (games-popularity.com/api-docs).

History endpoints return a game's points newest first, up to 1,000 per page,
with `nextCursor` (a timestamp) for the next, older page. Their times are UTC
without an offset, with 0 to 7 fractional digits.

Checked 2026-10-11: a game with no data returns 200 with `history: []`;
an app they do not track returns 404. Limits: about 1,000 requests a day
per key and per IP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .http import Client, HTTPStatusError

BASE = "https://games-popularity.com/swagger/api"
HOST = "games-popularity.com"
KINDS = ("followers", "players")

_FRACTION = re.compile(r"(\.\d{6})\d+")


def parse_time(raw: str) -> datetime:
    """Their timestamps as aware UTC datetimes (fractions past 6 digits are cut)."""
    return datetime.fromisoformat(_FRACTION.sub(r"\1", raw)).replace(tzinfo=timezone.utc)


@dataclass
class History:
    status: str                      # ok, null (no points), not_in_dataset (404)
    points: list[tuple[datetime, int]] = field(default_factory=list)  # newest first
    requests: int = 0
    complete: bool = True            # False if max_pages stopped it early
    next_cursor: str | None = None   # when not complete: the older page to resume from
    oldest: datetime | None = None   # oldest point seen (with or without a value)
    rate_limited: bool = False       # a later page got 429: the pages before it are kept


def history(client: Client, kind: str, appid: int, key: str, *, since: datetime | None = None,
            cursor: str | None = None, before: datetime | None = None, max_pages: int = 5) -> History:
    """Points for one game newer than `since` (all if None), paging back as needed.

    To resume a pull that stopped early, pass its `next_cursor` as `cursor` and
    its `oldest` as `before`: points at or after `before` are skipped, so a page
    boundary seen twice gives no duplicates.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    url = f"{BASE}/game/{kind}/{appid}"
    params = {"apiKey": key, **({"cursor": cursor} if cursor else {})}
    res = History(status="ok", oldest=before)
    while True:
        try:
            page = client.get_json(url, params)
        except HTTPStatusError as e:
            if e.status == 429 and res.requests:  # out of quota mid-pull: keep the pages already fetched
                res.requests += 1
                res.complete, res.next_cursor, res.rate_limited = False, params["cursor"], True
                return res
            if e.status != 404:
                raise
            res.requests += 1
            if "cursor" in params:  # odd, but keep the newer pages already fetched
                res.complete, res.next_cursor = False, params["cursor"]
                return res
            return History(status="not_in_dataset", requests=res.requests)
        res.requests += 1
        reached_since = False
        for p in page.get("history") or []:
            t = parse_time(p["added"])
            if since is not None and t <= since:
                reached_since = True
                break
            if res.oldest is not None and t >= res.oldest:
                continue  # already have it
            res.oldest = t
            if p.get(kind) is not None:
                res.points.append((t, int(p[kind])))
        nxt = page.get("nextCursor")
        if reached_since or not nxt:
            break
        if res.requests >= max_pages:
            res.complete, res.next_cursor = False, nxt
            break
        params = {"apiKey": key, "cursor": nxt}
    if not res.points and since is None and cursor is None:
        res.status = "null"
    return res


def value_at(points: list[tuple[datetime, int]], when: datetime) -> tuple[float, float] | None:
    """Value interpolated at `when` from the points just before and after it,
    with the hours between those two points. None if `when` is not inside the series."""
    before = [p for p in points if p[0] <= when]
    after = [p for p in points if p[0] > when]
    if not before or not after:
        return None
    (t0, v0), (t1, v1) = max(before), min(after)
    span = (t1 - t0).total_seconds()
    return v0 + (when - t0).total_seconds() / span * (v1 - v0), span / 3600
