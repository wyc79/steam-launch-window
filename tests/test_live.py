"""Smoke tests against the real endpoints. Run with: pytest -m live

One or two requests per endpoint. They check that the shapes we rely on
(docs/endpoints.md) still hold, so a Steam change fails loudly here
instead of quietly corrupting the data.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from pipeline import gp, steam
from pipeline.http import Client

pytestmark = pytest.mark.live

BALATRO = 2379780
BALATRO_LAUNCH = 1708440403


@pytest.fixture(scope="module")
def client():
    return Client(min_interval=1.5, max_retries=2)


def test_tag_list(client):
    version, tags = steam.tag_list(client)
    assert version and len(tags) > 300
    assert tags[492] == "Indie"


def test_query_coming_soon_page(client):
    payload_filters = {"coming_soon_only": True, "type_filters": steam.GAMES_ONLY,
                       "tagids_must_match": [{"tagids": [492]}, {"tagids": [1664]}]}
    items = steam.store_query(client, payload_filters, {"include_release": True, "include_tag_count": 5})
    assert len(items) > 500
    displays = {(i.get("release") or {}).get("coming_soon_display") for i in items}
    assert {"date_full", "date_month", "date_quarter", "date_year"} <= displays


def test_get_items_fields(client):
    items = steam.get_items(client, [BALATRO], {"include_release": True, "include_tag_count": 5,
                                                "include_basic_info": True, "include_reviews": True})
    it = items[BALATRO]
    assert it["release"]["steam_release_date"] == BALATRO_LAUNCH
    assert it["tags"][0]["weight"] > 0
    assert it["basic_info"]["developers"][0]["name"] == "LocalThunk"
    assert it["reviews"]["summary_filtered"]["review_count"] > 100_000


def test_wishlist_search_page(client):
    res = client.get_json(f"{steam.STORE}/search/results/", {
        "query": "", "start": 0, "count": 100, "filter": "popularwishlist", "infinite": 1, "cc": "us"})
    assert res["total_count"] > 1000
    assert len(steam.parse_search_appids(res["results_html"])) == 100


def test_review_window_count(client):
    counts = steam.review_counts(client, BALATRO, BALATRO_LAUNCH, BALATRO_LAUNCH + 30 * 86400)
    assert 10_000 < counts["total"] < 40_000
    assert counts["positive"] + counts["negative"] == counts["total"]


def test_games_popularity_follower_history(client):
    # The follower source (one request). The community follower page is no longer
    # checked: we do not collect from it, and shared runner IPs can be blocked there.
    key = os.environ.get("GP_API_KEY", "").strip()
    if not key:
        pytest.skip("GP_API_KEY not set")
    res = gp.history(client, "followers", BALATRO, key, max_pages=1)
    assert res.status == "ok" and res.requests == 1
    assert len(res.points) > 100  # one page of a long daily series
    newest, value = res.points[0]
    assert value > 10_000
    assert datetime.now(timezone.utc) - newest < timedelta(days=14)
