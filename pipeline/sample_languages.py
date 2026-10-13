"""Reviews by language for a sample of past launches (docs/phase2-plan.md, question 4).

    python -m pipeline.sample_languages --data-dir _data --budget-minutes 600

Picks paid launches (full or Early Access) from --since to 31 days before today
with at least --min-reviews reviews in their first 30 days: --games of them, half
supporting Simplified Chinese and half not, seeded. The first run saves the pick
to history/language_sample_games.csv and later runs reuse it, so a run that
resumes on another day (when other games have become eligible) counts the same
games. For each game it counts the first-30-day reviews (Steam
purchases, like reviews_30d) in every language of LANGUAGES and in all languages
together, so the shares share one denominator taken at the same time.

Writes history/reviews_by_language.csv: appid, schinese_supported, language,
reviews, positive, fetched. Resumable: pairs already in the file are skipped,
and progress is saved every 100 requests and on Ctrl+C or SIGTERM. A game with
no review data in all languages is recorded as empty in every language without
asking for each. Exit code 3
(with --fail-if-incomplete) when pairs are left, so a loop can run it again.
About 11 requests per game: 11,000 for the default 1,000 games.
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta

from . import steam, storage
from .collect_history import WINDOW
from .common import Budget, base_parser, run_pass, setup

LANGUAGES = ["all", "english", "schinese", "tchinese", "russian", "japanese", "koreana",
             "brazilian", "german", "french", "spanish"]
FIELDS = ["appid", "schinese_supported", "language", "reviews", "positive", "fetched"]
PICK_FIELDS = ["appid"]

log = logging.getLogger("sample_languages")


def pick(rows: list[dict], games: int, since: date, until: date, min_reviews: int, seed: int) -> list[dict]:
    """Half with Simplified Chinese, half without, from eligible paid launches; seeded."""
    eligible = [r for r in rows
                if r["launch_type"] in ("full", "early_access")
                and not steam.free_game(r.get("is_free"), steam.tag_ids(r.get("tags")))
                and since.isoformat() <= r["launch_date"] <= until.isoformat()
                and r.get("reviews_30d_source") == "api" and int(r.get("reviews_30d") or 0) >= min_reviews]
    groups = {True: [], False: []}
    for r in sorted(eligible, key=lambda r: int(r["appid"])):
        groups["schinese" in (r.get("languages") or "").split("|")].append(r)
    rng = random.Random(seed)
    chosen = []
    for supported in (True, False):
        g = groups[supported]
        chosen += rng.sample(g, min(games // 2, len(g)))
    return chosen


def main(argv=None) -> int:
    p = base_parser(__doc__)
    p.add_argument("--games", type=int, default=1000)
    p.add_argument("--since", type=date.fromisoformat, default=date(2023, 1, 1))
    p.add_argument("--min-reviews", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--budget-minutes", type=float, default=300)
    p.add_argument("--checkpoint", type=int, default=100)
    p.add_argument("--max-consecutive-errors", type=int, default=25)
    p.add_argument("--fail-if-incomplete", action="store_true",
                   help="exit with 3 if pairs are left, so a loop can run it again")
    args = p.parse_args(argv)
    client, today = setup(args)

    rows = storage.read_csv(args.data_dir / "history" / "games.csv")
    pick_path = args.data_dir / "history" / "language_sample_games.csv"
    saved = [r["appid"] for r in storage.read_csv(pick_path)]
    if saved:
        by_id = {r["appid"]: r for r in rows}
        games = [by_id[a] for a in saved if a in by_id]
        log.info("reusing the saved pick of %d games", len(games))
    else:
        games = pick(rows, args.games, args.since, today - timedelta(days=31), args.min_reviews, args.seed)
        storage.write_csv(pick_path, [{"appid": g["appid"]} for g in games], PICK_FIELDS)
    log.info("%d games picked (%d with Simplified Chinese)", len(games),
             sum("schinese" in (g.get("languages") or "").split("|") for g in games))
    path = args.data_dir / "history" / "reviews_by_language.csv"
    done = {(r["appid"], r["language"]): r for r in storage.read_csv(path)}
    todo = [(g, lang) for g in games for lang in LANGUAGES if (g["appid"], lang) not in done]
    log.info("%d pairs to count (%d already in the file)", len(todo), len(done))
    stamp = today.isoformat()

    def save():
        storage.write_csv(path, [done[k] for k in sorted(done, key=lambda k: (int(k[0]), LANGUAGES.index(k[1])
                                                                              if k[1] in LANGUAGES else 99))], FIELDS)

    def record(game, lang, counts):
        done[(game["appid"], lang)] = {
            "appid": game["appid"], "schinese_supported": int("schinese" in (game.get("languages") or "").split("|")),
            "language": lang, "reviews": counts["total"], "positive": counts["positive"], "fetched": stamp}

    def fetch(item):
        game, lang = item
        whole = done.get((game["appid"], "all"))
        if lang != "all" and whole is not None and whole["reviews"] == "":
            record(game, lang, {"total": "", "positive": ""})  # no data at all: no need to ask per language
            return False
        start = int(game["launch_ts"])
        try:
            counts = steam.review_counts(client, game["appid"], start, start + WINDOW, steam.PURCHASE_STEAM, lang)
        except steam.Unavailable:
            counts = {"total": "", "positive": ""}  # recorded as unknown, not retried
        record(game, lang, counts)
        return True

    finished = False
    try:
        finished = run_pass(todo, fetch, "reviews by language", Budget(args.budget_minutes), save,
                            checkpoint=args.checkpoint, max_consecutive_errors=args.max_consecutive_errors,
                            key=lambda item: f"{item[0]['appid']} {item[1]}")
    except KeyboardInterrupt:
        log.info("interrupted, saving progress")
    finally:
        save()
    left = sum((g["appid"], lang) not in done for g in games for lang in LANGUAGES)
    log.info("done: %d pairs left", left)
    return 3 if (args.fail_if_incomplete and (left or not finished)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
