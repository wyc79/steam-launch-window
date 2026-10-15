import json

import pytest

from pipeline import steam
from pipeline.http import HTTPStatusError

# Shapes copied from real IStoreBrowseService/GetItems responses (2026-10-10), trimmed.
BOLTGUN2 = {
    "appid": 3115160, "name": "Warhammer 40,000: Boltgun 2", "is_coming_soon": True,
    "release": {"steam_release_date": 1791993600, "is_coming_soon": True, "coming_soon_display": "date_full"},
    "tagids": [19, 1023537], "tags": [{"tagid": 19, "weight": 746}, {"tagid": 1023537, "weight": 730}],
    "basic_info": {"publishers": [{"name": "Big Fan Games"}, {"name": "Devolver Digital"}],
                   "developers": [{"name": "Auroch Digital"}], "franchises": [{"name": "Warhammer"}]},
    "related_items": {"demo_appid": [4338410]},
}


def release(display, ts=None, **extra):
    return {"release": {"coming_soon_display": display, "steam_release_date": ts, **extra}}


@pytest.mark.parametrize("item, raw, precision, start, end", [
    (BOLTGUN2, "Oct 14, 2026", "day", "2026-10-14", "2026-10-14"),
    (release("date_month", 1796025600), "November 2026", "month", "2026-11-01", "2026-11-30"),
    (release("date_quarter", 1798704000), "Q4 2026", "quarter", "2026-10-01", "2026-12-31"),
    (release("date_year", 1830240000), "2027", "year", "2027-01-01", "2027-12-31"),
    (release("text_tba", custom_release_date_message="To be announced"), "To be announced", "unknown", "", ""),
    (release("text_comingsoon"), "Coming soon", "unknown", "", ""),
])
def test_release_fields(item, raw, precision, start, end):
    f = steam.release_fields(item)
    assert (f["raw"], f["precision"], f["date"], f["date_end"], f["date_ok"]) == (raw, precision, start, end, 1)


def test_release_fields_uses_pacific_calendar_date():
    # 2026-10-15 03:00 UTC is still Oct 14 in Los Angeles
    f = steam.release_fields(release("date_full", 1792033200))
    assert f["date"] == "2026-10-14"


def test_release_fields_flags_disagreement():
    # A month-precision timestamp should point at the month's last day
    f = steam.release_fields(release("date_month", 1791993600))  # Oct 14
    assert f["date_ok"] == 0


def test_release_fields_early_access():
    assert steam.release_fields(release("date_full", 1791993600, is_early_access=True))["early_access"] == 1


def test_language_fields():
    item = {"supported_languages": [
        {"elanguage": 0, "supported": True, "full_audio": True},
        {"elanguage": 6, "supported": True, "full_audio": False},
        {"elanguage": 22, "supported": True},
        {"elanguage": 8, "supported": False},
        {"elanguage": 99, "supported": True},
        {"elanguage": -1, "eadditionallanguage": 53, "supported": True},
    ]}
    assert steam.language_fields(item) == {
        "languages": "english|schinese|brazilian|lang99|extra53", "audio_languages": "english"}
    assert steam.language_fields({}) == {"languages": "", "audio_languages": ""}


def test_meta_fields():
    m = steam.meta_fields(BOLTGUN2)
    assert m["developers"] == "Auroch Digital"
    assert m["publishers"] == "Big Fan Games|Devolver Digital"
    assert m["tags"] == "19:746|1023537:730"
    assert m["demo_appids"] == "4338410"


@pytest.mark.parametrize("item, cents", [
    ({"is_free": True}, 0),
    ({"best_purchase_option": {"final_price_in_cents": "2499"}}, 2499),
    ({"best_purchase_option": {"final_price_in_cents": "1249", "original_price_in_cents": "2499"}}, 2499),
    ({}, ""),
])
def test_price_cents(item, cents):
    assert steam.price_cents(item) == cents


def test_parse_search_appids_keeps_order():
    html = ('<a href="x" data-ds-appid="20" data-ds-itemkey="App_20">'
            '<a href="y" data-ds-appid="10" data-ds-itemkey="App_10">'
            '<a href="z" data-ds-packageid="5" data-ds-appid="1,2">')
    assert steam.parse_search_appids(html) == [20, 10]


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_json(self, url, params=None, cache_ttl=None, cache_if=None):
        q = json.loads(params["input_json"])["query"]
        self.calls.append(q)
        return {"response": self.pages[q["start"]]}


def page(appids, total):
    return {"metadata": {"total_matching_records": total},
            "ids": [{"appid": a} for a in appids], "store_items": [{"appid": a} for a in appids]}


def test_store_query_pages_with_stable_sort_and_dedupes(monkeypatch):
    monkeypatch.setattr(steam, "QUERY_PAGE", 2)
    client = FakeClient({0: page([1, 2], 5), 2: page([2, 3], 5), 4: page([4], 5)})
    items = steam.store_query(client, {}, {}, min_coverage=0.5)
    assert sorted(i["appid"] for i in items) == [1, 2, 3, 4]
    assert all(c["sort"] == steam.QUERY_SORT for c in client.calls)


def test_store_query_raises_when_items_go_missing(monkeypatch):
    monkeypatch.setattr(steam, "QUERY_PAGE", 2)
    client = FakeClient({0: page([1, 2], 6), 2: page([1, 2], 6), 4: page([1, 2], 6)})
    with pytest.raises(steam.IncompleteListing):
        steam.store_query(client, {}, {})


class SearchClient:
    """Fake store search: serves `total` appids, but only `per_page` rows per call."""

    def __init__(self, total, per_page):
        self.total, self.per_page, self.starts = total, per_page, []

    def get_json(self, url, params=None, cache_ttl=None, cache_if=None):
        start = params["start"]
        self.starts.append(start)
        ids = range(start + 1, min(start + self.per_page, self.total) + 1)
        html = "".join(f'<a data-ds-appid="{i}">' for i in ids)
        return {"success": 1, "total_count": self.total, "results_html": html}


def test_wishlist_ranking_advances_by_rows_returned():
    client = SearchClient(total=130, per_page=25)  # Steam sometimes returns fewer than asked
    assert steam.wishlist_ranking(client) == list(range(1, 131))
    assert client.starts[:3] == [0, 25, 50]


class ReviewsClient:
    """Serves one GetAppReviews reply (or raises it) and records the request."""

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def get_json(self, url, params=None):
        self.calls.append((url, json.loads(params["input_json"])))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


# Real IUserReviewsService/GetAppReviews replies (2026-10-11), reviews trimmed.
# Shroom and Gloom, first 30 days: the old appreviews call gave the same 1719 / 1604 / 115.
REVIEWS_WINDOW = {"response": {
    "query_summary": {"num_reviews": 1, "review_score": 8, "review_score_desc": "Very Positive",
                      "total_positive": 1604, "total_negative": 115, "total_reviews": 1719},
    "reviews": [{"recommendationid": "1", "timestamp_created": 1789100000, "voted_up": True}],
    "cursor": "AoJ4", "total_matching": 1719}}
REVIEWS_EMPTY_WINDOW = {"response": {
    "query_summary": {"num_reviews": 0, "review_score": 0, "review_score_desc": "No user reviews",
                      "total_positive": 0, "total_negative": 0, "total_reviews": 0},
    "cursor": "*", "total_matching": 0}}
REVIEWS_UNKNOWN_APP = {"response": {}}


def test_review_counts_reads_the_window_totals():
    client = ReviewsClient(REVIEWS_WINDOW)
    assert steam.review_counts(client, 3271280, 1789055435, 1789055435 + 30 * 86400) == {
        "total": 1719, "positive": 1604, "negative": 115}
    url, payload = client.calls[0]
    assert url == f"{steam.API}/IUserReviewsService/GetAppReviews/v1/"
    assert payload == {"appid": 3271280, "filter": 1, "languages": ["all"], "purchase_type": 0,
                       "num_per_page": 1, "date_range_start": 1789055435,
                       "date_range_end": 1789055435 + 30 * 86400}
    assert "cursor" not in payload and "key" not in payload  # totals come only on the first page


def test_review_counts_zero_in_window_is_a_real_zero():
    assert steam.review_counts(ReviewsClient(REVIEWS_EMPTY_WINDOW), 1, 0, 1) == {
        "total": 0, "positive": 0, "negative": 0}


@pytest.mark.parametrize("reply", [REVIEWS_UNKNOWN_APP, {}, {"response": {"query_summary": {"num_reviews": 0}}}])
def test_review_counts_raises_unavailable_without_totals(reply):
    with pytest.raises(steam.Unavailable):
        steam.review_counts(ReviewsClient(reply), 1, 0, 1)


def test_review_counts_passes_http_errors_up():
    with pytest.raises(HTTPStatusError):
        steam.review_counts(ReviewsClient(HTTPStatusError(429, "u")), 1, 0, 1)


def test_review_counts_sends_the_purchase_type_and_language():
    client = ReviewsClient(REVIEWS_WINDOW)
    steam.review_counts(client, 1, 0, 1, steam.PURCHASE_ALL, "schinese")
    _, payload = client.calls[0]
    assert payload["purchase_type"] == 1 and payload["languages"] == ["schinese"]


def test_demo_release_looks_up_each_linked_demo_once(monkeypatch):
    asked = []

    def get_items(client, ids, data_request, cache_ttl=None):
        asked.append(ids)
        return {30: {"release": {"steam_release_date": 100}}, 31: {"release": {}}}
    items = [{"related_items": {"demo_appid": [31, 30]}}, {"related_items": {"demo_appid": [30]}}, {}]
    monkeypatch.setattr(steam, "get_items", get_items)
    assert steam.demo_release(None, items) == {30: 100}  # 31 has no date
    assert asked == [[30, 31]]
    assert steam.first_demo([31, 30], {30: 100, 31: 50}) == 50
    assert steam.first_demo([7], {30: 100}) is None
