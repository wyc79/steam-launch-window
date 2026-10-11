"""Find a steady request pace steamcommunity.com tolerates for follower counts.

Run on the always-on box, with nothing else requesting follower pages from
the same network:  .venv/bin/python scripts/server/follower_pace_test.py
Results: .cache/pace/pace_log.csv (every request) and pace_followers.csv.

Phase 0: wait INITIAL_WAIT_H hours with no requests, then check every 2 h whether
the block has lifted, using games never requested before (a cached reply for a
recently requested game can return 200 while the IP is still blocked).
Phase 1: 1 request every 120 s for up to 6 h; stop at the first 429.
Phase 2: if phase 1 was clean, 1 request every 60 s for up to 6 h; stop at the first 429.

Every request uses a game never requested before, so cached replies cannot fake
a success. Each request is logged to pace_log.csv; follower counts (useful data,
merge later) go to pace_followers.csv.
"""
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import requests  # noqa: E402

from pipeline import collect_followers as cf, storage  # noqa: E402
from pipeline.http import USER_AGENT  # noqa: E402

OUT = REPO / ".cache" / "pace"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "pace_log.csv"
FOLLOWERS = OUT / "pace_followers.csv"

snapshot = storage.read_csv(cf.latest_snapshot_path(REPO / "_data"))
queue = [appid for _, appid in cf.plan(snapshot, {}, datetime.now(timezone.utc), cf.Policy())]
session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
done = 0


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


INITIAL_WAIT_H = 6
# Far end of the queue: games never requested, so no cached replies can fake a 200.
fresh = iter(reversed(queue))


def ask(phase, interval):
    """One request for the next never-requested game. Returns the HTTP status."""
    global done
    appid = next(fresh)
    try:
        r = session.get(f"https://steamcommunity.com/games/{appid}/memberslistxml/",
                        params={"xml": 1, "p": 99999}, timeout=30)
        status = r.status_code
    except requests.RequestException as e:
        status = f"error {type(e).__name__}"
    storage.append_csv(LOG, {"time": now(), "phase": phase, "interval_s": interval, "appid": appid,
                             "status": status}, ["time", "phase", "interval_s", "appid", "status"])
    if status == 200:
        m = re.search(r"<memberCount>\s*(\d+)\s*</memberCount>", r.text)
        storage.append_csv(FOLLOWERS, {"appid": appid, "followers": m.group(1) if m else "",
                                       "fetched_at": now()}, ["appid", "followers", "fetched_at"])
        done += 1
    print(f"{now()} phase {phase} interval {interval}s appid {appid} -> {status} (ok so far {done})", flush=True)
    return status


def steady(phase, interval, hours):
    """Ask every `interval` seconds for `hours`. True if no 429 happened."""
    end = time.monotonic() + hours * 3600
    while time.monotonic() < end:
        t = time.monotonic()
        status = ask(phase, interval)
        if status == 429:
            print(f"{now()} PHASE {phase} BLOCKED after {done} total ok", flush=True)
            return False
        time.sleep(max(0, interval - (time.monotonic() - t)))
    print(f"{now()} PHASE {phase} CLEAN: {hours} h at {interval}s", flush=True)
    return True


# Phase 0: quiet time, then check every 2 h with uncached games
print(f"{now()} waiting {INITIAL_WAIT_H} h with no requests", flush=True)
time.sleep(INITIAL_WAIT_H * 3600)
while ask(0, 7200) != 200:
    time.sleep(7200)
print(f"{now()} unblocked", flush=True)

if steady(1, 120, 6):
    steady(2, 60, 6)
print(f"{now()} test finished; {done} follower counts saved", flush=True)
