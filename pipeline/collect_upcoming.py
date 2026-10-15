"""Daily snapshot of every coming-soon game on Steam.

Outputs (under --data-dir):
  upcoming/snapshots/YYYY-MM-DD.csv.gz  one row per game: release date fields, wishlist rank
  upcoming/apps.csv                     latest name, developer, tags, demo per game ever seen;
                                        last_seen is the last day the game was coming soon,
                                        so a launched game's row shows its pre-launch metadata
  upcoming/runs.csv                     one line per day, for monitoring (a rerun replaces it)
  tags.csv                              tag id to name, in English and Simplified Chinese

Rerunning on the same day reuses cached pages, so a failed run can resume.
If the wishlist crawl fails, the snapshot is still written with empty ranks,
runs.csv says ranking_ok=0, and the exit code is 1.
"""

from __future__ import annotations

import collections
import logging
import time

from . import steam, storage
from .common import base_parser, setup

SNAPSHOT_FIELDS = ["appid", "release_ts", "display", "raw", "precision", "date", "date_end",
                   "date_ok", "early_access", "wishlist_rank", "price_cents"]
APP_FIELDS = ["appid", "name", "developers", "publishers", "franchises", "tags",
              "demo_appids", "is_free", "languages", "audio_languages", "first_seen", "last_seen"]
RUN_FIELDS = ["date", "games", "dated", "ranked", "ranked_not_listed", "date_mismatch",
              "requests", "seconds", "ranking_ok"]

DATA_REQUEST = {"include_release": True, "include_tag_count": 20, "include_basic_info": True,
                "include_supported_languages": True}
CACHE_TTL = 20 * 3600

log = logging.getLogger("collect_upcoming")


def build_snapshot(items: list[dict], ranking: list[int]) -> list[dict]:
    rank = {appid: i + 1 for i, appid in enumerate(ranking)}
    rows = []
    for it in items:
        row = {"appid": it["appid"], **steam.release_fields(it), "wishlist_rank": rank.get(it["appid"], ""),
               "price_cents": steam.price_cents(it)}
        rows.append(row)
    rows.sort(key=lambda r: r["appid"])
    return rows


def merge_apps(existing: list[dict], items: list[dict], today: str) -> list[dict]:
    by_id = {int(r["appid"]): r for r in existing}
    for it in items:
        old = by_id.get(it["appid"], {})
        by_id[it["appid"]] = {
            "appid": it["appid"], **steam.meta_fields(it),
            "first_seen": old.get("first_seen") or today,
            "last_seen": today,
        }
    return [by_id[a] for a in sorted(by_id)]


def main(argv=None) -> int:
    args = base_parser(__doc__).parse_args(argv)
    client, today = setup(args)
    t0 = time.monotonic()
    day = today.isoformat()
    out = args.data_dir

    _, tags = steam.tag_list(client)
    _, tags_zh = steam.tag_list(client, "schinese")  # the Chinese site's names; same ids
    storage.write_csv(out / "tags.csv",
                      [{"tagid": k, "name": v, "name_schinese": tags_zh.get(k, "")} for k, v in sorted(tags.items())],
                      ["tagid", "name", "name_schinese"])

    items = steam.store_query(client, {"coming_soon_only": True, "type_filters": steam.GAMES_ONLY},
                              DATA_REQUEST, cache_ttl=CACHE_TTL)
    log.info("coming-soon games: %d", len(items))
    try:
        ranking = steam.wishlist_ranking(client, cache_ttl=CACHE_TTL)
        ranking_ok = True
        log.info("wishlist-ranked games: %d", len(ranking))
    except Exception as e:  # noqa: BLE001 - keep the day's release dates even without ranks
        log.error("wishlist crawl failed (%s); writing the snapshot without ranks", e)
        ranking, ranking_ok = [], False

    snapshot = build_snapshot(items, ranking)
    storage.write_csv(out / "upcoming" / "snapshots" / f"{day}.csv.gz", snapshot, SNAPSHOT_FIELDS)

    apps_path = out / "upcoming" / "apps.csv"
    storage.write_csv(apps_path, merge_apps(storage.read_csv(apps_path), items, day), APP_FIELDS)

    listed = {r["appid"] for r in snapshot}
    precisions = collections.Counter(r["precision"] for r in snapshot)
    stats = {
        "date": day,
        "games": len(snapshot),
        "dated": len(snapshot) - precisions["unknown"],
        "ranked": sum(1 for r in snapshot if r["wishlist_rank"] != ""),
        "ranked_not_listed": sum(1 for a in ranking if a not in listed),
        "date_mismatch": sum(1 for r in snapshot if not r["date_ok"]),
        "requests": client.requests_made,
        "seconds": round(time.monotonic() - t0),
        "ranking_ok": int(ranking_ok),
    }
    storage.replace_row(out / "upcoming" / "runs.csv", stats, RUN_FIELDS, key="date")
    log.info("precision counts: %s", dict(precisions))
    log.info("run stats: %s", stats)
    return 0 if ranking_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
