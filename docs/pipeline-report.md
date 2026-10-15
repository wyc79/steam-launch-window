# Pipeline report: audit Phase 7 and build Phase 1

Date: 2026-10-12. Covers the data pipeline (build plan Phase 1) and the pipeline
audit (Phases 1 to 6, reported 2026-10-11 and 2026-10-12). Status of later work
lives in [roadmap.md](roadmap.md).

Numbers marked *measured* come from real runs or files on 2026-10-12. Numbers
marked *estimate* are projections and should be checked again after a month.

## Build Phase 1: what the spec asked for

| Spec item | Status |
|---|---|
| `collect_upcoming.py`: daily snapshot of every coming-soon game with tags, raw date, parsed date, precision, hype proxies; keep every snapshot | done. 60,227 games on 2026-10-12, 17,067 with a date, 5,262 with a wishlist rank. Followers come from Games Popularity (see B) |
| `collect_history.py`: launches of the last 3 to 5 years with tags, price, date, Early Access, demo, reviews in days 0 to 30 | done, since 2022-01-01: 83,219 games, 80,403 with a 30-day count. Also first-day and first-week counts (294 launches so far, filled as windows close) |
| `dateparse.py` with full unit tests | done, `tests/test_dateparse.py` |
| `events.yaml` with sources | done, 308 entries, each with a source and a confidence |
| GitHub Actions: daily snapshot, weekly history; small committed data | done and switched on 2026-10-12. Raw data on the `data` branch (gzip), Parquet copy on Hugging Face |
| Deliverables for this phase: README, `docs/endpoints.md`, tests | done. 261 offline tests pass; 6 live tests are kept apart (`pytest -m live`) |

## A. Repository audit

**Shape.** Small Python collectors that each write CSV files, run by GitHub
Actions and committed to an orphan `data` branch; a publisher rebuilds that
branch as Parquet on Hugging Face.

| Part | Code | Runs | Output |
|---|---|---|---|
| Upcoming snapshot | [collect_upcoming.py](../pipeline/collect_upcoming.py) | daily, 18:30 UTC, catch-up 21:47 | `upcoming/snapshots/DATE.csv.gz`, `apps.csv`, `runs.csv` |
| History | [collect_history.py](../pipeline/collect_history.py) | weekly, Monday | `history/games.csv` |
| Followers and players | [gp.py](../pipeline/gp.py), [collect_gp.py](../pipeline/collect_gp.py), [hf_sync.py](../pipeline/hf_sync.py) | daily, after the snapshot | `gp/` in the public dataset |
| Publisher | [publish_dataset.py](../pipeline/publish_dataset.py) | after each history run | Parquet and card on Hugging Face |
| Shared | [http.py](../pipeline/http.py), [storage.py](../pipeline/storage.py), [steam.py](../pipeline/steam.py) | | polite HTTP client, atomic writes |

**Strengths.** A tested HTTP client (per-host spacing, bounded retries, secrets
hidden from logs and cache). Atomic writes and deterministic gzip, so reruns
give identical files. Progress is saved on SIGTERM and on a timeout. Jobs that
touch the data are queued in one concurrency group. Every switch is a
repository variable, so a fork collects nothing until told to.

**Weaknesses found in the audit, and where they stand:**

| Finding | Now |
|---|---|
| Follower plan needed about 5,900 community requests a day; the community site blocks after about 60 | replaced by Games Popularity (one request per game gives its whole history) |
| History rows were dropped when a game left the listing | rows are kept; `first_listed` and `last_listed` added |
| An empty follower count meant two things | each pull has a status (`ok`, `null`, `not_in_dataset`, `stale`, `partial`, `error`) |
| One failed wishlist page lost the day's snapshot | the snapshot is saved with empty ranks and `ranking_ok=0`; the 21:47 run retries |
| `unavailable` review counts were never retried | retried after 90 days |
| No run logs for followers | `gp/runs.csv`: requests, results, why the run stopped |
| Publisher could delete any `--out` folder | refuses a folder it did not build |
| Upload could overwrite newer data or publish a broken build | names its parent revision; stops on a missing file, a dropped column or a table 5% smaller |
| Duplicate rows in `runs.csv` on reruns | one row per day |
| Schedules on the hour, one pending run per group | off the hour, `queue: max` |

**Verified bottlenecks today.** Only the Games Popularity request budget (see C).
Steam calls are cheap: 116 to 120 requests per snapshot (*measured*).

## B. Data sources

| Source | Gives | Cost and limits | Republishing | Use |
|---|---|---|---|---|
| Steam `IStoreQueryService/Query`, `IStoreBrowseService/GetItems` | coming-soon list, dates, tags, prices, demos | free, Steam Web API key | facts only; Valve has not licensed the data (see the card's Data rights) | **used** |
| Steam store search (wishlist sort) | wishlist rank, top ~5,300 | free, keyless | same | **used** |
| Steam `IUserReviewsService/GetAppReviews` | review counts by date window | free | same | **used** (old `appreviews` retires 2026-10-22) |
| [Games Popularity](https://games-popularity.com/api-docs) | follower history (daily, since 2024-03-15), player history (hourly) | free key. Docs: 1 request a second per key, no daily quota. Owner (2026-10-11): about 1,000 a day per key and IP; (2026-10-12) free limits to be cut, paid plan coming | **allowed by the owner, 2026-10-12**, with credit | **used** for followers and players |
| steamcommunity `memberslistxml` | current follower count | blocks an IP for 8+ hours after about 60 requests | | retired; kept for manual checks |
| Gamalytic | followers, estimates | 250 a day free, paid tiers | ToS forbids redistribution | not used |
| SteamDB | many | no API | forbids scraping | not used |
| IsThereAnyDeal | price history | free key | partly | optional, later |
| SteamSpy, IGDB, VG Insights, public datasets | weak or no follower data | | | not used |

**Best follower source:** Games Popularity. On 122 games its numbers matched our
own community counts within a median 0.06%. Two real runs (*measured*): 1,630
requests on 2026-10-12 with no 429, 677 games' follower series (71,393 points)
and 679 games' player series (287,103 points).

**Open questions:** what the new free limit will be; whether the cap counts per
UTC day or a rolling 24 hours; how stale small games get (19% of an early
sample were stale or empty).

## C. Ongoing cost

All jobs run on standard GitHub-hosted runners, which are free for public
repositories. API cost is $0 while Games Popularity stays free.

| Job | Requests | Runtime per run | Hours a month |
|---|---|---|---|
| Daily snapshot | ~120 Steam (*measured*) | ~3 min (156 to 173 s, *measured*) | ~1.5 |
| Daily Games Popularity | 900 (budget) | ~18 min (1,094 s for 900, *measured*) | ~9 |
| Catch-up run (21:47) | usually 0 | ~2 min setup | ~1 |
| Weekly history | a few hundred Steam | ~10 min (566 s, *measured*) | ~0.7 |
| Publish, events check, tests | 0 Steam | ~1 to 2 min | ~0.5 |
| **Total** | ~27,000 Games Popularity and ~5,000 Steam a month | | **~13 (expected)** |

Theoretical minimum: 1 request a second gives 15 min for Games Popularity and
2 min for the snapshot, about 9 hours a month. Expected is higher because of the
1.2 s spacing, retries and job setup.

**Games Popularity queue** (*measured* on 2026-10-12: 77,068 jobs due) and how
long it takes at 900 a day (*estimate*):

| Jobs | Due now | Time |
|---|---|---|
| Players, 35 to 60 days after launch | 1,911 | about 3 days |
| Followers, 8 days after launch | 4,531 | about 5 days |
| Upcoming games with a date or rank | 20,481 | about 23 days |
| Backfill since 2024-03-15 | 50,145 | about 4 months with what is left after the steady jobs (~420 a day) |

Steady state uses about 480 a day (players ~70, post-launch followers ~70,
upcoming refresh ~340). If the free limit drops below that, the 60-day refresh
must stretch and the backfill stops until it is raised.

**Storage:**

| Where | Now (*measured*) | Growth (*estimate*) |
|---|---|---|
| `data` branch | 57.5 MB packed, all versions (50 MB at HEAD, mostly `games.csv` 32 MB and `apps.csv` 17.5 MB) | ~110 MB a year of snapshots, plus deltas of the rewritten CSVs (not yet measured) |
| Hugging Face Parquet | 26.5 MB | ~10 to 15 MB a month of snapshots; weekly rewrites add ~1 GB a year of version history |
| Hugging Face `gp/` (gzip CSV) | 3.0 MB | ~2 MB a day during the backfill, under 1 MB a day after; ~0.3 to 0.5 GB the first year |

All of this should stay within GitHub's 1 GB guidance for a few years and within Hugging
Face's best-effort public storage.

## D. Hugging Face

As built (`strikeoo/steam-launch-data`, public):

- **Schema and partitions:** `history/games.parquet`, `upcoming/apps.parquet`,
  `upcoming/snapshots/YYYY-MM.parquet` (with `snapshot_date`),
  `upcoming/release_changes.parquet`, `upcoming/runs.parquet`, `tags.parquet`,
  `events.parquet`, and `gp/followers|players/YYYY-MM-DD.csv.gz` with
  `gp/state.csv` and `gp/runs.csv`, plus `gp_parquet/followers|players/YYYY-MM.parquet`,
  a weekly copy of the `gp/` points (the dataset viewer reads every config as Parquet).
  The card defines one config per table and says for each column whether it was
  observed at the time or is today's view.
- **Writers:** the publish job writes the Parquet files (`gp_parquet/` from a download
  of `gp/`) and the card after each history run; the daily job writes `gp/`. Both are in one concurrency group and
  both commit with a parent revision, so neither can overwrite the other. The
  publisher never deletes, and a test guards that.
- **Auth:** fine-grained `HF_TOKEN` secret with write access to the dataset.
- **Checks before upload:** manifest comparison (no missing file, no dropped
  column, no table more than 5% smaller); identical data gives identical files
  and card, so nothing is re-uploaded.
- **Migration done 2026-10-12:** the private `strikeoo/steam-launch-gp` files
  were copied to `gp/` and checked byte for byte; the daily job and a publish
  then ran against the public dataset. The private dataset was deleted the same day.

Not built: Trusted Publisher login (OIDC, no stored token). The token works; this
would only remove a secret.

## E. Research readiness

The data supports a study of whether launches in busier niche weeks get fewer
reviews: every launch since 2022 with its competition, reviews in the first
day, week and 30 days, events, and pre-launch followers for launches since
mid-2024. Players in the first month are a second outcome for launches from
mid-August 2026 on.

Limits that remain: tags and prices in `history` are today's values (look-ahead
for past launches; the frozen `apps.csv` rows fix it from October 2026 on);
competition is what launched, not what was announced when the date was picked
(snapshots start 2026-10-11); delisted games before 2026-10 are missing;
reviews stand in for sales. Results must be worded as associations.

The cheap changes from Phase 5 are all built: `last_seen`, `first_listed` and
`last_listed`, first-day and first-week reviews, player history, per-column
time notes. Nothing more is worth adding now.

## F. Changes made

PRs #13 (audit Phase 6), #14 (fixes from the first Games Popularity run) and #15
(Games Popularity data public, publish after history), all merged 2026-10-12.

**Files:** all collectors and `http.py`, `storage.py`, `steam.py`, `common.py`;
new `gp.py`, `collect_gp.py`, `hf_sync.py`, `scripts/compare_followers.py`;
`publish_dataset.py`; all five workflows; README, `endpoints.md`,
`phase2-plan.md`, `roadmap.md`, server README; tests for each.

**Implemented and tested, also run for real on GitHub:**
- daily snapshot (two runs, `ranking_ok=1`);
- weekly history on top of the Pi backfill (no rows lost, 294 first-week counts);
- Games Popularity collector: budget stop, players first, saved progress on a
  cancel (two manual runs, and a third after the day's budget was spent);
- sync with the public dataset, including the `gp/state.csv` requirement;
- publish with upload, manifest check and the `gp_` configs on the card;
- `queue: max` in the shared concurrency group.

**Implemented and tested offline, not yet seen in a real run:**
- the 21:47 catch-up skipping a finished day (first chance tonight);
- the publish starting from a finished history run (first chance Monday
  2026-10-19);
- the stop on a persistent 429 from Games Popularity (the cap was never hit);
- the 90-day retry of `unavailable` reviews;
- the endpoint check on GitHub (switch off, see G). Its new Games Popularity
  test passed locally with one request.

**Recommended, not built:**
- Trusted Publisher login for Hugging Face.
- First-day and first-week review counts for launches since 2022 (an optional
  Pi job, about 100,000 requests; command in the server README).
- Quarterly tags on the dataset (for example `v2026.10`) so a paper can cite a
  fixed version.

**Blocked:**
- A faster Games Popularity backfill: needs the whitelist or a paid plan.

**Compatibility:** new columns are added at the end of each file and old files
still read. The `GP_DATASET_REPO` variable is no longer used. The Pi runs an old
checkout: pull `main` before running any review job there after 2026-10-22.

## G. Next actions for you

1. Drop the user-wide write scope from `HF_TOKEN`; it only needs write access to
   `strikeoo/steam-launch-data` now.
2. Delete the `GP_DATASET_REPO` repository variable (the private dataset is
   already deleted).
3. Remove the finished Pi backfill service
   (`systemctl --user disable --now steam-history-backfill`).
4. When Games Popularity announces the new limits, tell me the number; I will
   set `GP_DAILY_BUDGET` and re-plan the queue. Decide then whether a paid plan
   is worth it for the backfill.
5. Read the dataset card's Data rights section once, now that it credits Games
   Popularity.
6. Turn on `ENDPOINT_CHECK`. It sends about 10 requests a week from a GitHub
   runner: Steam endpoints plus one Games Popularity request. The community
   follower test was dropped (we no longer use that source, and shared runner
   IPs can be blocked there).
7. Optional: set up a Trusted Publisher on the dataset (repository
   `wyc79/steam-launch-window`, workflow files `collect-daily.yml` and
   `publish-dataset.yml`).
8. Around 2026-11-07: replace the 2027 China holiday estimates in `events.yaml`.

Then build Phase 2 (analysis) can start: first answer the 4 open questions in
[phase2-plan.md](phase2-plan.md).
