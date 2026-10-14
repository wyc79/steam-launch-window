# steam-launch-window

A tool that helps indie developers pick a Steam launch week.

Give it your game's Steam tags. It shows which upcoming weeks are crowded or
quiet in that niche, marks Steam sales and fests, and shows how similar past
launches did depending on when they launched.

Website: <https://wyc79.github.io/steam-launch-window/> (live since 2026-10-14;
see [Website](#website)).

Status: **Phase 3 (website)**. The data pipeline (Phase 1) and the analysis
(Phase 2) are done and run on a schedule. Website steps 1 to 5 are merged: the
page with its four sections, the most anticipated list (PR #30) and the Methods
page. Step 6, the deploy workflow (PR #31), went live on 2026-10-14; a review of
the live site follows. The
recommendation agent (Phase 4) comes after. See [docs/roadmap.md](docs/roadmap.md).

## Why

Launch timing is one of the few things a small team fully controls. Most
advice is folklore ("never launch during a sale"). This project collects the
data to check it per niche, and is honest about what the data can and cannot say.

## Data sources

Steam's own public endpoints, plus [Games Popularity](https://games-popularity.com)
for follower and player history. No logins. Details, quirks and test results
are in [docs/endpoints.md](docs/endpoints.md).

| What | Where from |
|---|---|
| Every upcoming game, its tags and release date | `IStoreQueryService/Query` |
| Hype: wishlist rank (top ~5,300 games) | Steam's "Top Wishlisted" search list |
| Hype: follower history | [Games Popularity](https://games-popularity.com) API: Steam community hub followers, daily since 2024-03-15 |
| Past launches since 2022 | `IStoreQueryService/Query` with a release date filter |
| Reviews in the first day, week and 30 days | `IUserReviewsService/GetAppReviews` with a date range (replaced `appreviews`, retired 2026-10-22) |
| Players in the first month | [Games Popularity](https://games-popularity.com) API, hourly |
| Steam sales, fests, major releases, holidays | [data/events.yaml](data/events.yaml), kept by hand, checked by `python -m pipeline.events` |

## How it runs

Python scripts collect the data. GitHub Actions run them on a schedule and
commit the results to the `data` branch.

| Script | Schedule | What it does |
|---|---|---|
| `pipeline.collect_upcoming` | daily | snapshot of all ~60,000 coming-soon games (about 2.5 min, 120 requests) |
| `pipeline.collect_gp` | daily, after the snapshot | follower and player history from Games Popularity, within a daily budget (see below) |
| `pipeline.collect_history` | weekly | lists games released since 2022, adds review counts for new ones |
| `analysis.model` | weekly, after the history job | fits the launch model and commits `site/model.json` to the `data` branch, for the website |
| `site` workflow | after the daily job, the model run and site changes on `main` | builds the website and deploys it to GitHub Pages |

The history backfill is a long one-off job (about a day at 1 request per
second). It runs outside Actions, on an always-on server
([scripts/server](scripts/server/README.md)). Actions only do the small daily
and weekly increments. The daily job has a second, later run that redoes the
snapshot if the first one was missed or its wishlist crawl failed.

Scheduled jobs are off until switched on with repository variables
(Settings > Secrets and variables > Actions > Variables), so a fresh fork
does not start collecting:

| Variable | Turns on |
|---|---|
| `COLLECT_DAILY=on` | the daily snapshot |
| `COLLECT_GP=on` | the Games Popularity step in the daily job (also needs the `GP_API_KEY` and `HF_TOKEN` secrets and the `HF_DATASET_REPO` variable; `GP_DAILY_BUDGET` is optional, default 900) |
| `COLLECT_HISTORY=on` | the weekly history job |
| `ENDPOINT_CHECK=on` | the weekly endpoint smoke test (Steam endpoints, plus one Games Popularity request with the `GP_API_KEY` secret) |
| `PUBLISH_DATASET=on` | the weekly upload to Hugging Face, which starts when the weekly history job ends (also needs the `HF_TOKEN` secret and `HF_DATASET_REPO` variable) |
| `MODEL_RUN=on` | the weekly model run, which starts when the weekly history job ends (reads the follower files from the public `HF_DATASET_REPO`; no token) |
| `DEPLOY_SITE=on` | the website build and deploy after the daily job, the model run and site changes on `main` (reads `gp/latest_followers.csv` from the public `HF_DATASET_REPO`; needs Settings > Pages > Source set to "GitHub Actions" once) |

Each workflow can also be run by hand from the Actions tab.

One workflow runs without a switch because it makes no requests: `events check`
validates `data/events.yaml` every Monday and fails (so GitHub emails you) when
an estimated event, such as a holiday whose official dates are not out yet,
starts within 90 days.

All scripts wait between requests to the same host (1 s by default, 2 s for
the store site on GitHub's servers, 1.2 s for Games Popularity), retry with
backoff on errors, and save progress as they go. Run one again and it
continues where it stopped. A 429 that persists after the retries stops the run.

### Followers and players

Wishlist rank is the main hype signal. Followers are a second one. Steam's
community site blocks an IP for many hours after about 60 requests, so
follower counts come from [Games Popularity](https://games-popularity.com).
Their numbers match ours (median gap 0.06% on 122 games), and one request
returns a game's whole daily follower series, so how often a game is pulled
only decides how fresh its newest value is. Their free API allows about 1,000
requests a day (the owner said on 2026-10-12 that free limits will be cut and a
paid plan added; lower `GP_DAILY_BUDGET` to match). The daily job uses up to 900,
in this order:

1. players 35 to 60 days after each launch (hourly counts for the first month;
   first, because a game missed by day 60 loses them for good)
2. followers about 8 days after each launch (the whole pre-launch series)
3. every upcoming game with a date or a wishlist rank, once every 60 days
4. the rest backfills games launched since 2024-03-15, paid games with 10+ reviews first

A pull that gets nothing new (a failed request, no data yet, or a launch week
Games Popularity has not reached) is retried after 1, 2, 4, 8 and 16 days, then
left alone. A history longer than 5 pages is fetched over several runs, from
where the last one stopped. A day that ended with a 429 is not retried until
the next UTC day. Manual scripts with the same key (`scripts/compare_followers.py`)
count against the same 1,000 a day but are not in the job's count: keep them
under 100 a day.

This data is republished, with the owner's permission (2026-10-12), under `gp/`
in the public Hugging Face dataset, which the daily job also uses as its storage.
`pipeline.collect_followers`, the old community scraper, is kept for occasional
manual checks, and `scripts/compare_followers.py` compares the two sources.

## Run it yourself

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev,hf]"

pytest                        # offline tests
pytest -m live                # a few real requests to check the endpoints still work

python -m pipeline.collect_upcoming
python -m pipeline.collect_gp --dry-run          # without --dry-run it needs GP_API_KEY
python -m pipeline.collect_history --since 2026-01-01 --budget-minutes 30
```

Outputs go to `_data/` (in CI this is the `data` branch). Games Popularity
data goes to `_gp/`.

## Website

A static site (Vite and plain JavaScript, in `site/`) at
<https://wyc79.github.io/steam-launch-window/>. The `site` workflow
(`.github/workflows/site.yml`) rebuilds and deploys it after each daily
snapshot, after the weekly model run, and when the site changes on `main`.

One-time setup (done on 2026-10-14):
1. Settings > Pages > Build and deployment > Source: "GitHub Actions".
2. Repository variable `DEPLOY_SITE=on`.
3. Run the `site` workflow once by hand from the Actions tab.

Build and preview it locally, from a checkout of the `data` branch in `_data/`:

```bash
cd site
npm ci
npm run data                  # data files into public/data (see site/README.md)
npm run dev                   # http://localhost:5173/steam-launch-window/
npm run build
npm run preview -- --port 5050   # serves dist/ at http://localhost:5050/steam-launch-window/
```

`vite preview` uses port 4173 by default, which Windows sometimes reserves
(an "access denied" error when it starts). Any free port works with `--port`.

## Public dataset

Once switched on, a weekly job publishes the `data` branch as Parquet files on
Hugging Face (`pipeline/publish_dataset.py`), with a dataset card that repeats
the caveats below and says when each value was observed. Daily snapshots are
grouped into one file per month. Before each upload the new files are checked
against the published ones (no missing file, no dropped column, no table 5%
smaller), and the upload fails instead of overwriting a change made in between.

## Data layout

`data` branch:

```
tags.csv                              tag id, name
upcoming/snapshots/YYYY-MM-DD.csv.gz  one row per coming-soon game per day:
                                      release date (raw, date, date_end, precision),
                                      Early Access flag, wishlist rank, price if set
upcoming/apps.csv                     name, developers, publishers, tags with weights,
                                      demo, supported and full-audio languages,
                                      first_seen, last_seen (last day coming soon)
upcoming/runs.csv                     one line per day (a rerun replaces it)
followers/latest.csv                  newest community follower count per game
followers/snapshots/YYYY-MM-DD.csv.gz community counts fetched that day
history/games.csv                     one row per game released since 2022:
                                      launch date and type, price, tags, languages,
                                      demo, reviews in the first day, week and 30 days,
                                      first_listed, last_listed (rows are never dropped)
site/model.json                       the launch model's output (analysis/model.py), weekly
```

Games Popularity data (under `gp/` in the public Hugging Face dataset, synced by the daily job):

```
followers/YYYY-MM-DD.csv.gz           points fetched that day: appid, followers,
                                      observed_at (their time), fetched_at (ours)
players/YYYY-MM-DD.csv.gz             the same, with players
latest_followers.csv                  the newest point per game: appid, followers, observed_at
state.csv                             per game: last pull and try, status, newest point,
                                      tries in a row without new points, where an
                                      unfinished pull goes on
runs.csv                              one line per run: requests, results, why it stopped
```

Release dates: Steam gives a timestamp plus a precision (day, month, quarter,
year, or none). For "November 2026" the range is Nov 1 to Nov 30. All dates
are in Pacific time, like the store.

## Limitations

- **No wishlist counts.** Steam does not publish them. Wishlist rank only
  covers the top ~5,300 games; followers are the only hype number for the rest.
- **Followers come from a third party.** Games Popularity history starts on
  2024-03-15, and some small games have gaps or stale values. Each pull records
  a status: `ok`, `null`, `not_in_dataset`, `stale`, `error`, or `partial`
  (a long series still being fetched; `resume_cursor` in `state.csv` marks the
  gap until it is filled). A game is only complete when its status is not
  `partial` and `resume_cursor` is empty.
- **History is today's view of the past.** Price, demo, tags and Early Access
  status are as they are now, not as they were at launch. A demo removed after
  launch is invisible. Deleted reviews are not counted. Games delisted before
  collection started are missing. For games launched from October 2026 on, the
  daily snapshots and the frozen `upcoming/apps.csv` row show the pre-launch state.
- **Early Access is messy.** Some games that left Early Access only tell us the
  1.0 date. Those rows are marked `launch_type=ea_exit` and should be analysed apart.
- **Reviews are a proxy for sales,** and for paid games only Steam purchases
  count. Free games count every review (`reviews_purchase=all`).

## Credits

Follower and player history: [Games Popularity](https://games-popularity.com).

## License

MIT for the code. The license does not cover the data: it comes from Steam,
owned by Valve, which has not licensed or endorsed this project, so the dataset
on Hugging Face is marked `license: other` and grants no license.
Games Popularity data is republished there with its owner's permission (2026-10-12).
