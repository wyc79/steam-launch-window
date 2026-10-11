import pytest
import requests

from pipeline.http import Client, HTTPStatusError


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
