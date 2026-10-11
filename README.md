# steam-launch-window

A tool that helps indie developers pick a Steam launch week.

Give it your game's Steam tags. It shows which upcoming weeks are crowded or
quiet in that niche, marks Steam sales and fests, and shows how similar past
launches did depending on when they launched.

Status: **Phase 1 (data pipeline)**. The analysis, the website and the
recommendation agent come next.

## Why

Launch timing is one of the few things a small team fully controls. Most
advice is folklore ("never launch during a sale"). This project collects the
data to check it per niche, and is honest about what the data can and cannot say.

## Data sources

Only Steam's own public endpoints. No logins. Details, quirks and test
results are in [docs/endpoints.md](docs/endpoints.md).

| What | Where from |
|---|---|
| Every upcoming game, its tags and release date | `IStoreQueryService/Query` |
| Hype: wishlist rank (top ~5,300 games) | Steam's "Top Wishlisted" search list |
| Hype: follower count | the game's community hub member count |
| Past launches since 2022 | `IStoreQueryService/Query` with a release date filter |
| Reviews in the first 30 days | `appreviews` with a date range |
| Steam sales, fests, big releases | [data/events.yaml](data/events.yaml), kept by hand |

## How it runs

Python scripts collect the data. GitHub Actions run them on a schedule and
commit the results to the `data` branch.

| Script | Schedule | What it does |
|---|---|---|
| `pipeline.collect_upcoming` | daily | snapshot of all ~60,000 coming-soon games (about 2.5 min, 120 requests) |
| `pipeline.collect_followers` | daily, after the snapshot | refreshes follower counts that are due (see below) |
| `pipeline.collect_history` | weekly | lists games released since 2022, adds 30-day review counts for new ones |

The first full follower scrape and the history backfill are long one-off
jobs (about a day each at 1 request per second). They run outside Actions,
on a local machine or an always-on server ([scripts/server](scripts/server/README.md)).
Actions only do the small daily and weekly increments.

Scheduled jobs are off until switched on with repository variables
(Settings > Secrets and variables > Actions > Variables), so a fresh fork
does not start scraping:

| Variable | Turns on |
|---|---|
| `COLLECT_DAILY=on` | the daily snapshot |
| `COLLECT_FOLLOWERS=on` | the follower step inside the daily job |
| `COLLECT_HISTORY=on` | the weekly history job |
| `ENDPOINT_CHECK=on` | the weekly endpoint smoke test |

Each workflow can also be run by hand from the Actions tab.

All scripts wait at least 1 second between requests to the same host (2 s
for the store site on GitHub's servers, 5 s for the community site), retry
with backoff on errors, and save progress as they go. Run one again and it
continues where it stopped. A 429 from the community site stops the run at
once, because retrying while blocked makes the block last longer.

### Follower refresh tiers

Wishlist rank is the main hype signal. Followers are a second one, and they
cost one request per game on a host that rate-limits hard, so only about
11,000 games are tracked: games on the Top Wishlisted list, plus games with a
day or month release date ending within 26 weeks. A tracked game is refreshed:

- daily if its date range ends within 8 weeks (or already passed), or it has 10,000+ followers
- every 3 days if its range ends within weeks 8 to 26
- weekly otherwise (wishlisted games that are further out or undated)

## Run it yourself

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev]"

pytest                        # offline tests
pytest -m live                # a few real requests to check the endpoints still work

python -m pipeline.collect_upcoming
python -m pipeline.collect_followers --budget-minutes 30
python -m pipeline.collect_history --since 2026-01-01 --budget-minutes 30
```

Outputs go to `_data/` (in CI this is the `data` branch).

## Data layout (`data` branch)

```
tags.csv                              tag id, name
upcoming/snapshots/YYYY-MM-DD.csv.gz  one row per coming-soon game per day:
                                      release date (raw, date, date_end, precision),
                                      Early Access flag, wishlist rank
upcoming/apps.csv                     name, developers, publishers, tags with weights, demo
upcoming/runs.csv                     one line per daily run
followers/latest.csv                  newest follower count per game
followers/snapshots/YYYY-MM-DD.csv.gz counts fetched that day
history/games.csv                     one row per game released since 2022:
                                      launch date and type, price, tags, demo,
                                      reviews in the first 30 days
```

Release dates: Steam gives a timestamp plus a precision (day, month, quarter,
year, or none). For "November 2026" the range is Nov 1 to Nov 30. All dates
are in Pacific time, like the store.

## Limitations

- **No wishlist counts.** Steam does not publish them. Wishlist rank only
  covers the top ~5,300 games; followers are the only hype number for the rest.
- **History is today's view of the past.** Price, demo and Early Access status
  are as they are now, not as they were at launch. A demo removed after launch
  is invisible. Deleted reviews are not counted. Delisted games are missing.
- **Early Access is messy.** Some games that left Early Access only tell us the
  1.0 date. Those rows are marked `launch_type=ea_exit` and should be analysed apart.
- **Reviews are a proxy for sales,** and only for Steam purchases.

## License

MIT
