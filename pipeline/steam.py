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
                              cache_ttl=cache_ttl)["response"]
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


_SEARCH_ROW = re.compile(r'data-ds-appid="(\d+)"')


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
        }, cache_ttl=cache_ttl)
        total = res.get("total_count", 0)
        page = parse_search_appids(res.get("results_html", ""))
        if not page:
            break
        for a in page:
            if a not in seen:
                seen.add(a)
                ranked.append(a)
        start += SEARCH_PAGE
    if total and len(ranked) < 0.99 * total:
        raise IncompleteListing(f"wishlist ranking got {len(ranked)} of {total}")
    return ranked


def tag_list(client: Client) -> tuple[str, dict[int, str]]:
    res = client.get_json(f"{API}/IStoreService/GetTagList/v1/", {"language": "english"})["response"]
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


def review_counts(client: Client, appid: int, start_ts: int, end_ts: int) -> dict:
    """Review totals for reviews written in [start_ts, end_ts] that still exist.

    Counts Steam purchases only, with Steam's default off-topic filter,
    which is how the store's own review count works. Reviews from key
    activations (often curator or giveaway copies) are left out.
    """
    res = client.get_json(f"{STORE}/appreviews/{appid}", {
        "json": 1, "filter": "recent", "language": "all", "purchase_type": "steam",
        "num_per_page": 0,
        "start_date": start_ts, "end_date": end_ts, "date_range_type": "include",
    })
    if res.get("success") != 1:
        raise ValueError(f"appreviews failed for {appid}: {res}")
    q = res["query_summary"]
    return {"total": q.get("total_reviews", 0), "positive": q.get("total_positive", 0),
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


def meta_fields(item: dict) -> dict:
    """Slow-changing descriptive fields for one store item."""
    basic = item.get("basic_info") or {}
    tags = item.get("tags") or [{"tagid": t, "weight": 0} for t in item.get("tagids") or []]
    demos = (item.get("related_items") or {}).get("demo_appid") or []
    return {
        "name": item.get("name", ""),
        "developers": _names(basic.get("developers")),
        "publishers": _names(basic.get("publishers")),
        "franchises": _names(basic.get("franchises")),
        "tags": "|".join(f"{t['tagid']}:{t.get('weight', 0)}" for t in tags),
        "demo_appids": "|".join(str(d) for d in demos),
        "is_free": int(bool(item.get("is_free"))),
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
