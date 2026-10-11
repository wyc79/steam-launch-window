"""Check that Games Popularity follower counts match our own Steam community counts.

For each game in a follower file we collected (appid, followers, fetched_at),
fetch its Games Popularity history and interpolate the value at our fetch time.

    python scripts/compare_followers.py ~/.cache/pi/followers/latest.csv [--limit 60]

One request per game, 1.2 s apart; they count toward the ~1,000 a day limit.
Needs GP_API_KEY (environment or .env). Prints a summary; --out saves every row as CSV.
First run (2026-10-11, 118 games): median difference 0.06%, 116 within 1%.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline import gp, storage  # noqa: E402
from pipeline.http import Client  # noqa: E402


def api_key() -> str:
    key = os.environ.get("GP_API_KEY", "")
    env = REPO / ".env"
    if not key and env.exists():
        pairs = dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line)
        key = pairs.get("GP_API_KEY", "")
    if not key.strip().strip('"'):
        raise SystemExit("set GP_API_KEY")
    return key.strip().strip('"')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ours", type=Path, help="CSV with appid, followers, fetched_at")
    p.add_argument("--limit", type=int, default=60, help="at most this many games (requests)")
    p.add_argument("--out", type=Path, help="save per-game rows here")
    args = p.parse_args(argv)
    key = api_key()
    client = Client(host_intervals={gp.HOST: 1.2}, host_max_retries={gp.HOST: 2})

    rows = []
    for r in [r for r in storage.read_csv(args.ours) if r["followers"]][:args.limit]:
        ours, at = int(r["followers"]), datetime.fromisoformat(r["fetched_at"])
        res = gp.history(client, "followers", int(r["appid"]), key)
        hit = gp.value_at(res.points, at)
        row = {"appid": r["appid"], "ours": ours, "fetched_at": r["fetched_at"], "status": res.status,
               "gp": round(hit[0]) if hit else "", "bracket_hours": round(hit[1], 1) if hit else "",
               "diff_pct": round(100 * (hit[0] - ours) / ours, 3) if hit and ours else ""}
        rows.append(row)
        print(row, flush=True)

    if args.out:
        storage.write_csv(args.out, rows, list(rows[0]) if rows else ["appid"])
    diffs = [abs(r["diff_pct"]) for r in rows if r["diff_pct"] != ""]
    print(f"\n{len(rows)} games, {len(diffs)} comparable, {len(rows) - len(diffs)} without GP points around our time")
    if diffs:
        print(f"median |diff| {statistics.median(diffs):.3f}%, within 0.5%: {sum(d <= 0.5 for d in diffs)}, "
              f"within 1%: {sum(d <= 1 for d in diffs)}, max {max(diffs):.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
