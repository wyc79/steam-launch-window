"""Publish the data branch as a Parquet dataset on Hugging Face.

Builds a folder like this from --data-dir, then uploads it:

  history/games.parquet                 one row per launch since 2022
  upcoming/apps.parquet                 names, tags, languages of every upcoming game seen
  upcoming/snapshots/YYYY-MM.parquet    every daily snapshot of that month (snapshot_date column)
  followers/latest.parquet              newest follower count per game
  followers/snapshots/YYYY-MM.parquet   every follower count fetched that month
  tags.parquet, events.parquet
  README.md                             dataset card

Needs the `publish` extra (pandas, pyarrow, huggingface_hub). Uploading needs
HF_TOKEN in the environment and --repo-id; --dry-run only builds the folder.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from . import collect_followers, collect_history, collect_upcoming

log = logging.getLogger("publish_dataset")

INT_COLUMNS = {
    "appid", "tagid", "release_ts", "date_ok", "early_access", "wishlist_rank", "price_cents",
    "is_free", "followers", "launch_ts", "steam_release_ts", "early_access_now",
    "demo_release_ts", "demo_before_launch", "reviews_total_now", "reviews_30d",
    "reviews_30d_positive", "reviews_before_launch",
}
DATE_COLUMNS = {"date", "date_end", "launch_date", "first_seen", "snapshot_date",
                "reviews_30d_fetched", "prior_check_fetched", "start", "end"}


def typed(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Integers as nullable Int64, ISO dates as dates, everything else as text.

    With `columns`, missing ones are added empty, so files written at
    different times (before and after a column was added) share one schema.
    """
    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[[c for c in df.columns if c not in columns] + columns]
    for col in df.columns:
        if col in INT_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif col in DATE_COLUMNS:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif col == "fetched_at":
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
        else:
            df[col] = df[col].astype("string")
    return df


def read(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return typed(pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""]), columns)


def write(df: pd.DataFrame, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return len(df)


def monthly(src_dir: Path, out_dir: Path, columns: list[str]) -> dict[str, int]:
    """Combine YYYY-MM-DD.csv.gz files into YYYY-MM.parquet with a snapshot_date column."""
    by_month: dict[str, list[Path]] = defaultdict(list)
    for f in sorted(src_dir.glob("*.csv.gz")):
        by_month[f.name[:7]].append(f)
    counts = {}
    for month, files in by_month.items():
        parts = []
        for f in files:
            df = read(f, columns)
            df.insert(0, "snapshot_date", pd.to_datetime(f.name[:10]).date())
            parts.append(df)
        counts[month] = write(pd.concat(parts, ignore_index=True), out_dir / f"{month}.parquet")
    return counts


def build(data_dir: Path, events_path: Path, out: Path, license_id: str) -> dict:
    if out.exists():
        shutil.rmtree(out)
    stats = {}
    simple = {
        "history/games.parquet": (data_dir / "history" / "games.csv", collect_history.FIELDS),
        "upcoming/apps.parquet": (data_dir / "upcoming" / "apps.csv", collect_upcoming.APP_FIELDS),
        "followers/latest.parquet": (data_dir / "followers" / "latest.csv", collect_followers.FIELDS),
        "tags.parquet": (data_dir / "tags.csv", ["tagid", "name"]),
    }
    for dest, (src, columns) in simple.items():
        if src.exists():
            stats[dest] = write(read(src, columns), out / dest)
    snapshot_columns = {"upcoming": collect_upcoming.SNAPSHOT_FIELDS, "followers": collect_followers.FIELDS}
    for name, columns in snapshot_columns.items():
        months = monthly(data_dir / name / "snapshots", out / name / "snapshots", columns)
        if months:
            stats[f"{name}/snapshots"] = months
    events = yaml.safe_load(events_path.read_text(encoding="ascii"))["events"]
    stats["events.parquet"] = write(typed(pd.DataFrame(events)), out / "events.parquet")
    (out / "README.md").write_text(card(stats, license_id), encoding="utf-8")
    return stats


def card(stats: dict, license_id: str) -> str:
    # (config name, files, key in stats); configs with no data yet are left out
    configs = [
        ("history", "history/games.parquet", "history/games.parquet"),
        ("upcoming_snapshots", "upcoming/snapshots/*.parquet", "upcoming/snapshots"),
        ("upcoming_apps", "upcoming/apps.parquet", "upcoming/apps.parquet"),
        ("followers", "followers/snapshots/*.parquet", "followers/snapshots"),
        ("events", "events.parquet", "events.parquet"),
        ("tags", "tags.parquet", "tags.parquet"),
    ]
    present = [(name, files) for name, files, key in configs if key in stats]
    meta = {
        "license": license_id,
        "pretty_name": "Steam Launch Window Data",
        "tags": ["steam", "video-games", "game-releases", "time-series"],
        "configs": [{"config_name": n, "data_files": p} for n, p in present],
    }

    def rows(key):
        v = stats.get(key)
        return sum(v.values()) if isinstance(v, dict) else (v or 0)

    snap_months = sorted(stats.get("upcoming/snapshots", {}))
    updated = datetime.now(timezone.utc).date().isoformat()
    return f"""---
{yaml.safe_dump(meta, sort_keys=False).strip()}
---

# Steam Launch Window Data

Data behind [steam-launch-window](https://github.com/wyc79/steam-launch-window),
a tool that helps indie developers pick a Steam launch week. Updated weekly.
Last update: {updated}.

Not affiliated with or endorsed by Valve. All data comes from Steam's public
store pages and endpoints, collected politely (rate-limited, no logins).
No personal data: no Steam IDs, usernames or review texts, only counts.

## What is here

| Config | Rows | What |
|---|---|---|
| `history` | {rows("history/games.parquet"):,} | games launched on Steam since 2022: launch date and type, price, tags, languages, demo, reviews in the first 30 days |
| `upcoming_snapshots` | {rows("upcoming/snapshots"):,} | one row per coming-soon game per day ({snap_months[0] if snap_months else "-"} to {snap_months[-1] if snap_months else "-"}): release date and its precision, Early Access, wishlist rank, price if set |
| `upcoming_apps` | {rows("upcoming/apps.parquet"):,} | name, developers, publishers, tags with vote weights, languages, demo |
| `followers` | {rows("followers/snapshots"):,} | community hub follower counts for tracked upcoming games, with fetch time |
| `events` | {rows("events.parquet"):,} | Steam sales, Next Fests, themed fests, big releases, regional holidays, each with a source |
| `tags` | {rows("tags.parquet"):,} | Steam tag id to name |

```python
from datasets import load_dataset
history = load_dataset("<this repo>", "history")
```

## Things to know before using it

- **Dates** are Pacific time. Fuzzy release dates ("Q3 2027") have a
  `precision` and a `date` to `date_end` range.
- **Reviews** are Steam-purchase reviews (key activations excluded), counted for
  the 30 days after launch, as they exist today (deleted reviews are gone).
- **History is today's view of the past.** Price, demo and Early Access
  status are as they are now. Delisted games are missing.
- **`launch_type`**: `full`, `early_access`, or `ea_exit` (a 1.0 launch of a
  game that was already on sale in Early Access; treat these apart).
- **Wishlist rank** only covers Steam's top ~5,300 wishlisted games.
  **Followers** are only tracked for about 11,000 upcoming games.
- **Upcoming prices** are almost always missing: paid games set them at launch.

Full methods: [README](https://github.com/wyc79/steam-launch-window#readme) and
[endpoint notes](https://github.com/wyc79/steam-launch-window/blob/main/docs/endpoints.md).
"""


def upload(out: Path, repo_id: str, token: str) -> None:
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
    stamp = datetime.now(timezone.utc).date().isoformat()
    api.upload_folder(folder_path=str(out), repo_id=repo_id, repo_type="dataset",
                      commit_message=f"Weekly update {stamp}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("_data"))
    p.add_argument("--events", type=Path, default=Path("data/events.yaml"))
    p.add_argument("--out", type=Path, default=Path(".cache/dataset"))
    p.add_argument("--repo-id", default=os.environ.get("HF_DATASET_REPO", ""),
                   help="Hugging Face dataset, e.g. user/steam-launch-data")
    p.add_argument("--license", default="cc-by-4.0")
    p.add_argument("--dry-run", action="store_true", help="build the folder but do not upload")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    stats = build(args.data_dir, args.events, args.out, args.license)
    log.info("built %s: %s", args.out, stats)
    if args.dry_run:
        return 0
    token = os.environ.get("HF_TOKEN")
    if not token or not args.repo_id:
        raise SystemExit("set HF_TOKEN and --repo-id (or HF_DATASET_REPO) to upload, or use --dry-run")
    upload(args.out, args.repo_id, token)
    log.info("uploaded to https://huggingface.co/datasets/%s", args.repo_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
