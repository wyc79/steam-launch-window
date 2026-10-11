import pytest
import requests

from pipeline.http import Client, HTTPStatusError, RateLimited


class FakeResponse:
    def __init__(self, status=200, text="{}", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}


class FakeSession:
    """Returns scripted responses in order; an Exception in the script is raised."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeTime:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def clock(self):
        return self.t


def make(script, **kw):
    ft = FakeTime()
    session = FakeSession(script)
    kw.setdefault("min_interval", 1.0)
    c = Client(session=session, sleep=ft.sleep, clock=ft.clock, now=ft.clock, **kw)
    return c, session, ft


def test_sets_user_agent():
    c, session, _ = make([])
    assert "steam-launch-window" in session.headers["User-Agent"]


def test_get_json_returns_parsed_body():
    c, session, _ = make([FakeResponse(text='{"a": 1}')])
    assert c.get_json("https://x.test/a", {"q": 1}) == {"a": 1}
    assert session.calls == [("https://x.test/a", {"q": 1})]


def test_spaces_requests_to_same_host_but_not_different_hosts():
    c, _, ft = make([FakeResponse()] * 3, min_interval=2.0)
    c.get_text("https://a.test/1")
    c.get_text("https://a.test/2")
    c.get_text("https://b.test/1")
    assert ft.sleeps == [2.0]


def test_per_host_interval_override():
    c, _, ft = make([FakeResponse()] * 2, min_interval=1.0, host_intervals={"a.test": 5.0})
    c.get_text("https://a.test/1")
    c.get_text("https://a.test/2")
    assert ft.sleeps == [5.0]


def test_retries_429_using_retry_after():
    c, session, ft = make([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(text="ok")], min_interval=0)
    assert c.get_text("https://a.test/") == "ok"
    assert len(session.calls) == 2
    assert 7 in ft.sleeps


def test_retries_5xx_and_connection_errors_with_growing_backoff():
    c, session, ft = make([
        FakeResponse(503), requests.ConnectionError("boom"), requests.Timeout("slow"), FakeResponse(text="ok"),
    ], min_interval=0, backoff_base=2.0)
    assert c.get_text("https://a.test/") == "ok"
    backoffs = [s for s in ft.sleeps if s > 0]
    assert len(backoffs) == 3
    assert backoffs == sorted(backoffs)


def test_gives_up_after_max_retries():
    c, session, _ = make([FakeResponse(500)] * 3, min_interval=0, max_retries=2)
    with pytest.raises(HTTPStatusError) as e:
        c.get_text("https://a.test/")
    assert e.value.status == 500
    assert len(session.calls) == 3


def test_does_not_retry_other_4xx():
    c, session, _ = make([FakeResponse(403)], min_interval=0)
    with pytest.raises(HTTPStatusError) as e:
        c.get_text("https://a.test/")
    assert e.value.status == 403
    assert len(session.calls) == 1


def test_error_message_hides_key_param():
    c, _, _ = make([FakeResponse(403)], min_interval=0, max_retries=0)
    with pytest.raises(HTTPStatusError) as e:
        c.get_text("https://a.test/", {"key": "SECRET", "x": 1})
    assert "SECRET" not in str(e.value)


def test_cache_hit_skips_network(tmp_path):
    c, session, ft = make([FakeResponse(text="first")], cache_dir=tmp_path)
    assert c.get_text("https://a.test/", {"p": 1}, cache_ttl=60) == "first"
    ft.t += 30
    assert c.get_text("https://a.test/", {"p": 1}, cache_ttl=60) == "first"
    assert len(session.calls) == 1


def test_cache_expires(tmp_path):
    c, session, ft = make([FakeResponse(text="first"), FakeResponse(text="second")], cache_dir=tmp_path)
    c.get_text("https://a.test/", cache_ttl=60)
    ft.t += 61
    assert c.get_text("https://a.test/", cache_ttl=60) == "second"


def test_cache_key_ignores_api_key_value(tmp_path):
    c, session, _ = make([FakeResponse(text="first")], cache_dir=tmp_path)
    c.get_text("https://a.test/", {"key": "A"}, cache_ttl=60)
    assert c.get_text("https://a.test/", {"key": "B"}, cache_ttl=60) == "first"
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert "A" not in f.read_text().split('"body"')[0].replace("a.test", "")


def test_429_from_a_stop_host_raises_at_once():
    c, session, _ = make([FakeResponse(429)], min_interval=0, stop_on_429_hosts={"a.test"})
    with pytest.raises(RateLimited):
        c.get_text("https://a.test/")
    assert len(session.calls) == 1


def test_retry_after_longer_than_cap_is_not_retried_early():
    c, session, ft = make([FakeResponse(429, headers={"Retry-After": "3600"})], min_interval=0, backoff_cap=300)
    with pytest.raises(RateLimited) as e:
        c.get_text("https://a.test/")
    assert e.value.retry_after == 3600
    assert len(session.calls) == 1


def test_get_json_does_not_cache_bad_bodies(tmp_path):
    c, session, _ = make([FakeResponse(text="<html>oops</html>"), FakeResponse(text='{"ok": 1}')], cache_dir=tmp_path)
    with pytest.raises(ValueError):
        c.get_json("https://a.test/", cache_ttl=60)
    assert c.get_json("https://a.test/", cache_ttl=60) == {"ok": 1}
    assert len(session.calls) == 2


def test_get_json_cache_if_rejects_semantic_failures(tmp_path):
    c, session, _ = make([FakeResponse(text='{"success": 2}'), FakeResponse(text='{"success": 1}')], cache_dir=tmp_path)
    ok = lambda d: d["success"] == 1  # noqa: E731
    assert c.get_json("https://a.test/", cache_ttl=60, cache_if=ok) == {"success": 2}
    assert c.get_json("https://a.test/", cache_ttl=60, cache_if=ok) == {"success": 1}
    assert c.get_json("https://a.test/", cache_ttl=60, cache_if=ok) == {"success": 1}  # now cached
    assert len(session.calls) == 2


def test_error_message_and_cache_hide_api_key_param(tmp_path):
    c, _, _ = make([FakeResponse(text="ok"), FakeResponse(404)], min_interval=0, cache_dir=tmp_path)
    c.get_text("https://a.test/", {"apiKey": "SECRET", "x": 1}, cache_ttl=60)
    for f in tmp_path.rglob("*.json"):
        assert "SECRET" not in f.read_text()
    with pytest.raises(HTTPStatusError) as e:
        c.get_text("https://a.test/other", {"apiKey": "SECRET"})
    assert "SECRET" not in str(e.value)


def test_retry_after_as_http_date():
    # 2026-10-11 12:00:30 GMT is 30 s after the fake clock's "now"
    c, session, ft = make([FakeResponse(429, headers={"Retry-After": "Sun, 11 Oct 2026 12:00:30 GMT"}),
                           FakeResponse(text="ok")], min_interval=0)
    c._now = lambda: 1791720000.0  # 2026-10-11 12:00:00 UTC
    assert c.get_text("https://a.test/") == "ok"
    assert 30 in ft.sleeps


def test_per_host_retry_limit():
    c, session, _ = make([FakeResponse(500)] * 5, min_interval=0, max_retries=4, host_max_retries={"a.test": 1})
    with pytest.raises(HTTPStatusError):
        c.get_text("https://a.test/")
    assert len(session.calls) == 2
