"""A polite HTTP client for Steam endpoints.

- One User-Agent that says who we are.
- Minimum spacing between requests to the same host.
- Retries with exponential backoff on 429, 5xx and network errors,
  honoring Retry-After.
- Optional on-disk cache, so a rerun on the same day resumes cheaply.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

USER_AGENT = "steam-launch-window/0.1 (+https://github.com/wyc79/steam-launch-window)"
RETRY_STATUSES = {429, 500, 502, 503, 504}
SECRET_PARAMS = {"key"}

log = logging.getLogger(__name__)


class HTTPStatusError(Exception):
    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url


def _public_params(params: dict | None) -> dict:
    return {k: v for k, v in (params or {}).items() if k not in SECRET_PARAMS}


def _describe(url: str, params: dict | None) -> str:
    p = _public_params(params)
    return f"{url}?{urlencode(p)}"[:300] if p else url


class Client:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        host_intervals: dict[str, float] | None = None,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        backoff_cap: float = 300.0,
        timeout: float = 60.0,
        cache_dir: str | Path | None = None,
        user_agent: str = USER_AGENT,
        session=None,
        sleep=time.sleep,
        clock=time.monotonic,
        now=time.time,
    ):
        self.min_interval = min_interval
        self.host_intervals = host_intervals or {}
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._sleep, self._clock, self._now = sleep, clock, now
        self._last_request: dict[str, float] = {}
        self.requests_made = 0

    # -- public -----------------------------------------------------------

    def get_text(self, url: str, params: dict | None = None, *, cache_ttl: float | None = None) -> str:
        if cache_ttl and (hit := self._cache_read(url, params, cache_ttl)) is not None:
            return hit
        body = self._fetch(url, params)
        if cache_ttl:
            self._cache_write(url, params, body)
        return body

    def get_json(self, url: str, params: dict | None = None, *, cache_ttl: float | None = None):
        return json.loads(self.get_text(url, params, cache_ttl=cache_ttl))

    # -- internals --------------------------------------------------------

    def _wait_for_host(self, host: str) -> None:
        interval = self.host_intervals.get(host, self.min_interval)
        last = self._last_request.get(host)
        if last is not None:
            wait = interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    def _backoff(self, attempt: int) -> float:
        base = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        return base * (1 + 0.25 * random.random())

    def _fetch(self, url: str, params: dict | None) -> str:
        host = urlsplit(url).netloc
        for attempt in range(self.max_retries + 1):
            self._wait_for_host(host)
            self.requests_made += 1
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.max_retries:
                    raise
                delay = self._backoff(attempt)
                log.warning("network error (%s) on %s, retry in %.0fs", type(e).__name__, _describe(url, params), delay)
                self._sleep(delay)
                continue

            if 200 <= r.status_code < 300:
                return r.text
            if r.status_code not in RETRY_STATUSES or attempt == self.max_retries:
                raise HTTPStatusError(r.status_code, _describe(url, params))

            delay = self._backoff(attempt)
            retry_after = r.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = min(self.backoff_cap, max(delay, float(retry_after)))
            log.warning("HTTP %s on %s, retry in %.0fs", r.status_code, _describe(url, params), delay)
            self._sleep(delay)
        raise AssertionError("unreachable")

    def _cache_path(self, url: str, params: dict | None) -> Path:
        key = url + "?" + urlencode(sorted(_public_params(params).items()))
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}.json"

    def _cache_read(self, url, params, ttl) -> str | None:
        if not self.cache_dir:
            return None
        path = self._cache_path(url, params)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self._now() - entry["t"] > ttl:
            return None
        return entry["body"]

    def _cache_write(self, url, params, body: str) -> None:
        if not self.cache_dir:
            return
        path = self._cache_path(url, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        entry = {"t": self._now(), "url": _describe(url, params), "body": body}
        tmp.write_text(json.dumps(entry), encoding="utf-8")
        tmp.replace(path)
