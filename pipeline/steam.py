"""Wrappers for the Steam endpoints verified in docs/endpoints.md."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from . import dateparse
from .http import Client

STORE = "https://store.steampowered.com"
API = "https://api.steampowered.com"
COMMUNITY = "https://steamcommunity.com"
CONTEXT = {"language": "english", "country_code": "US", "steam_realm": 1}
PACIFIC = ZoneInfo("America/Los_Angeles")

QUERY_PAGE = 1000      # max page size for IStoreQueryService/Query
QUERY_SORT = 2         # a sort that pages completely (default sort skips items)
GET_ITEMS_BATCH = 200  # 300 ids overflows the URL
SEARCH_PAGE = 100

GAMES_ONLY = {"include_games": True}

log = logging.getLogger(__name__)


class IncompleteListing(Exception):
    """A paged listing returned fewer unique items than it said it had."""


class Unavailable(Exception):
    """Steam answered, but has no data for this app (removed, hidden, region-locked).
    Retrying will not help, so callers record it instead of trying forever."""


def _input_json(payload: dict) -> dict:
    return {"input_json": json.dumps(payload, separators=(",", ":"))}


# -- store listings ----------------------------------------------------------

def store_query(client: Client, filters: dict, data_request: dict, *,
                min_coverage: float = 0.999, cache_ttl: float | None = None) -> list[dict]:
    """All items matching `filters`, paged with a stable sort.

    Raises IncompleteListing if fewer than `min_coverage` of the reported
    total came back, since the analysis depends on complete counts.
    """
    items: dict[int, dict] = {}
    start, total = 0, None
    while True:
        payload = {
            "query": {"start": start, "count": QUERY_PAGE, "sort": QUERY_SORT, "filters": filters},
            "context": CONTEXT,
            "data_request": data_request,
        }
        res = client.get_json(f"{API}/IStoreQueryService/Query/v1/", _input_json(payload),
                              cache_ttl=cache_ttl,
                              cache_if=lambda d: "metadata" in d.get("response", {}))["response"]
        total = res.get("metadata", {}).get("total_matching_records", 0)
        page = res.get("store_items") or []
        for it in page:
            items.setdefault(it["appid"], it)
        start += len(res.get("ids") or [])
        if not page or start >= total:
            break
    if total and len(items) < min_coverage * total:
        raise IncompleteListing(f"got {len(items)} of {total} items for filters {filters}")
    if len(items) != total:
        log.warning("listing returned %d unique items, metadata said %d", len(items), total)
    return list(items.values())


def get_items(client: Client, appids: list[int], data_request: dict, *,
              cache_ttl: float | None = None) -> dict[int, dict]:
    """Store items by appid. Missing or hidden apps are left out."""
    out: dict[int, dict] = {}
    for i in range(0, len(appids), GET_ITEMS_BATCH):
        batch = appids[i:i + GET_ITEMS_BATCH]
        payload = {"ids": [{"appid": a} for a in batch], "context": CONTEXT, "data_request": data_request}
        res = client.get_json(f"{API}/IStoreBrowseService/GetItems/v1/", _input_json(payload),
                              cache_ttl=cache_ttl)["response"]
        for it in res.get("store_items") or []:
            if it.get("success") == 1 and "appid" in it:
                out[it["appid"]] = it
    return out


def demo_appids(item: dict) -> list[int]:
    return [int(d) for d in (item.get("related_items") or {}).get("demo_appid") or []]


def demo_release(client: Client, items, *, cache_ttl: float | None = None) -> dict[int, int]:
    """Release time of each demo the items link to. A demo Steam no longer lists, or
    one with no date, is left out."""
    ids = sorted({d for it in items for d in demo_appids(it)})
    demos = get_items(client, ids, {"include_release": True}, cache_ttl=cache_ttl)
    return {a: d["release"]["steam_release_date"] for a, d in demos.items()
            if (d.get("release") or {}).get("steam_release_date")}


def first_demo(demo_ids: list[int], release: dict[int, int]) -> int | None:
    """The earliest release time among a game's demos, or None."""
    return min((release[d] for d in demo_ids if d in release), default=None)


_SEARCH_ROW = re.compile(r'data-ds-appid="(\d+)"')
_SEARCH_ROW_ANY = re.compile(r'data-ds-appid="[^"]*"')  # bundles too, for counting rows


def parse_search_appids(results_html: str) -> list[int]:
    """Appids in page order from a store search `results_html` fragment.

    Bundles have a comma list in data-ds-appid; those are skipped.
    """
    return [int(a) for a in _SEARCH_ROW.findall(results_html)]


def wishlist_ranking(client: Client, *, cache_ttl: float | None = None) -> list[int]:
    """Appids ordered by Steam's "Top Wishlisted" list (rank 1 first)."""
    ranked: list[int] = []
    seen: set[int] = set()
    start, total = 0, None
    while total is None or start < total:
        res = client.get_json(f"{STORE}/search/results/", {
            "query": "", "start": start, "count": SEARCH_PAGE, "filter": "popularwishlist",
            "infinite": 1, "cc": "us", "l": "english",
        }, cache_ttl=cache_ttl, cache_if=lambda d: d.get("success") == 1 and d.get("results_html"))
        total = res.get("total_count", 0)
        rows = _SEARCH_ROW_ANY.findall(res.get("results_html", ""))
        if not rows:
            break
        for a in parse_search_appids(res.get("results_html", "")):
            if a not in seen:
                seen.add(a)
                ranked.append(a)
        start += len(rows)  # Steam does not always return exactly `count` rows
    if total and len(ranked) < 0.99 * total:
        raise IncompleteListing(f"wishlist ranking got {len(ranked)} of {total}")
    return ranked


def tag_list(client: Client, language: str = "english") -> tuple[str, dict[int, str]]:
    res = client.get_json(f"{API}/IStoreService/GetTagList/v1/", {"language": language})["response"]
    return res.get("version_hash", ""), {t["tagid"]: t["name"] for t in res.get("tags", [])}


# -- per-app lookups ---------------------------------------------------------

_MEMBER_COUNT = re.compile(r"<memberCount>\s*(\d+)\s*</memberCount>")


def follower_count(client: Client, appid: int) -> int | None:
    """Members of the app's community hub ("followers").

    Asks for a page past the end so the reply has the count but no
    member Steam IDs. Returns None if the reply has no count (no hub).
    HTTP and network errors are raised so the caller can retry later.
    """
    text = client.get_text(f"{COMMUNITY}/games/{appid}/memberslistxml/", {"xml": 1, "p": 99999})
    m = _MEMBER_COUNT.search(text)
    return int(m.group(1)) if m else None


FREE_TO_PLAY = 113  # Steam tag id


def tag_ids(raw: str) -> list[int]:
    """'id:weight|...' as ids, heaviest first (ties by id)."""
    pairs = [(int(t), int(w or 0)) for t, _, w in (p.partition(":") for p in (raw or "").split("|") if p)]
    return [t for t, _ in sorted(pairs, key=lambda p: (-p[1], p[0]))]


def free_game(flag, tags: list[int]) -> bool:
    """Free if Steam flags it, or "Free to Play" is among its 10 heaviest tags (the tag
    catches free games that have not set the flag). This is today's status."""
    return str(flag) == "1" or FREE_TO_PLAY in tags[:10]


PURCHASE_STEAM = 0  # reviewers who bought the game on Steam (the store's own count)
PURCHASE_ALL = 1    # everyone, including key activations and free-to-play players
# (2 is "not bought on Steam"; checked 2026-10-12: Balatro's first 30 days 19,248 + 2,260 = 21,508,
# Marvel Rivals' 0 + 123,761 = 123,761, since nobody buys a free game)


def review_counts(client: Client, appid: int, start_ts: int, end_ts: int,
                  purchase_type: int = PURCHASE_STEAM, language: str = "all") -> dict:
    """Review totals for reviews written in [start_ts, end_ts] (both ends included) that still exist.

    By default counts Steam purchases only, with Steam's default off-topic
    filter, which is how the store's own review count works. Reviews from key
    activations (often curator or giveaway copies) are left out. Free games
    need PURCHASE_ALL: their players buy nothing, so a purchases-only count is
    near zero. `language` is one Steam language code (e.g. "schinese") or "all".

    Uses IUserReviewsService/GetAppReviews, which replaces store appreviews
    (retired 2026-10-22). No key: keyless calls share a lower rate limit and
    get 429 past it. Checked 2026-10-11 on 4 games: totals, positive and
    negative equal the old endpoint's. The totals only come on the first page,
    so no cursor is sent; num_per_page=1 keeps the reply small (0 means 20).
    """
    res = client.get_json(f"{API}/IUserReviewsService/GetAppReviews/v1/", _input_json({
        "appid": appid, "filter": 1, "languages": [language], "purchase_type": purchase_type, "num_per_page": 1,
        "date_range_start": start_ts, "date_range_end": end_ts,
    })).get("response") or {}
    q = res.get("query_summary")
    if not q or "total_reviews" not in q:  # unknown or removed apps get an empty response
        raise Unavailable(f"GetAppReviews has no data for {appid}: {res}")
    return {"total": q["total_reviews"], "positive": q.get("total_positive", 0),
            "negative": q.get("total_negative", 0)}


# -- turning store items into flat fields ------------------------------------

_MONTH_ABBR = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_MONTH_FULL = ("January February March April May June July August "
               "September October November December").split()


def pacific_date(ts: int):
    return datetime.fromtimestamp(ts, PACIFIC).date()


def display_string(release: dict) -> str:
    """The release date as the US English store shows it.

    Rebuilt from Steam's structured fields, so it is exactly what
    search results display ("Oct 21, 2026", "November 2026", "Q4 2026", "2026").
    """
    display = release.get("coming_soon_display")
    ts = release.get("steam_release_date")
    if release.get("custom_release_date_message"):
        return release["custom_release_date_message"]
    if display == "text_comingsoon":
        return "Coming soon"
    if display == "text_tba":
        return "To be announced"
    if not ts:
        return ""
    d = pacific_date(ts)
    if display == "date_month":
        return f"{_MONTH_FULL[d.month - 1]} {d.year}"
    if display == "date_quarter":
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    if display == "date_year":
        return str(d.year)
    # date_full, or released games which have no display mode
    return f"{_MONTH_ABBR[d.month - 1]} {d.day}, {d.year}"


def release_fields(item: dict) -> dict:
    """Release date fields for one store item.

    `date_ok` is False when our parse of the display string disagrees with
    Steam's timestamp (for fuzzy dates the timestamp is the period's last day).
    """
    rel = item.get("release") or {}
    raw = display_string(rel)
    parsed = dateparse.parse(raw)
    ts = rel.get("steam_release_date")
    date_ok = True
    if ts and parsed.precision != dateparse.UNKNOWN:
        date_ok = parsed.end == pacific_date(ts)
    return {
        "release_ts": ts or "",
        "display": rel.get("coming_soon_display") or "",
        "raw": raw,
        "precision": parsed.precision,
        "date": parsed.date.isoformat() if parsed.date else "",
        "date_end": parsed.end.isoformat() if parsed.end else "",
        "date_ok": int(date_ok),
        "early_access": int(bool(rel.get("is_early_access"))),
    }


def _names(entries) -> str:
    return "|".join(e.get("name", "") for e in entries or [])


# Steam's ELanguage numbers. Checked against the store's language list for
# Boltgun 2 and Hades (codes 0-8, 10, 12, 19, 22); the rest follow Steam's enum.
LANGUAGES = {
    0: "english", 1: "german", 2: "french", 3: "italian", 4: "korean", 5: "spanish",
    6: "schinese", 7: "tchinese", 8: "russian", 9: "thai", 10: "japanese", 11: "portuguese",
    12: "polish", 13: "danish", 14: "dutch", 15: "finnish", 16: "norwegian", 17: "swedish",
    18: "hungarian", 19: "czech", 20: "romanian", 21: "turkish", 22: "brazilian",
    23: "bulgarian", 24: "greek", 25: "arabic", 26: "ukrainian", 27: "latam",
    28: "vietnamese", 29: "indonesian",
}


def _language_name(entry: dict) -> str:
    code = entry["elanguage"]
    if code == -1:  # one of Steam's extra languages, numbered separately; names not verified
        return f"extra{entry.get('eadditionallanguage')}"
    return LANGUAGES.get(code, f"lang{code}")


def language_fields(item: dict) -> dict:
    """Supported languages (interface or subtitles) and full-audio languages, pipe-joined."""
    langs = [l for l in item.get("supported_languages") or [] if l.get("supported")]
    name = _language_name
    return {
        "languages": "|".join(name(l) for l in langs),
        "audio_languages": "|".join(name(l) for l in langs if l.get("full_audio")),
    }


def meta_fields(item: dict) -> dict:
    """Slow-changing descriptive fields for one store item."""
    basic = item.get("basic_info") or {}
    tags = item.get("tags") or [{"tagid": t, "weight": 0} for t in item.get("tagids") or []]
    demos = demo_appids(item)
    return {
        "name": item.get("name", ""),
        "developers": _names(basic.get("developers")),
        "publishers": _names(basic.get("publishers")),
        "franchises": _names(basic.get("franchises")),
        "tags": "|".join(f"{t['tagid']}:{t.get('weight', 0)}" for t in tags),
        "demo_appids": "|".join(str(d) for d in demos),
        "is_free": int(bool(item.get("is_free"))),
        **language_fields(item),
    }


def price_cents(item: dict) -> int | str:
    """Undiscounted current US price in cents, or "" if not for sale."""
    if item.get("is_free"):
        return 0
    bpo = item.get("best_purchase_option") or {}
    for key in ("original_price_in_cents", "final_price_in_cents"):
        if bpo.get(key) not in (None, ""):
            return int(bpo[key])
    return ""
