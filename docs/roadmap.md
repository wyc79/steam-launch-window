# Roadmap and status

Last updated: 2026-10-11.

Two plans have run in parallel:
- **The build plan** (Phases 0 to 4): endpoints, data pipeline, analysis, website, agent.
- **The pipeline audit** (Phases 1 to 7): audit, other data sources, costs, Hugging Face,
  research readiness, implementation, deliverables.

The audit's implementation phase is how the build plan's Phase 1 gets finished. After that,
the build plan continues with Phase 2. Every phase ends with a report, and the next one
starts only after a go-ahead.

| Plan | Phase | Status |
|---|---|---|
| Build | 0. Endpoint discovery | done 2026-10-10 |
| Build | 1. Data pipeline | code merged (PRs #1 to #12); backfill finishing; final report waits for the audit fixes |
| Audit | 1 to 4. Audit, sources, costs, Hugging Face | reported 2026-10-11 |
| Audit | 5. Research readiness | reported 2026-10-11 |
| Audit | 6. Implementation | built on branch `phase6-audit` 2026-10-11; **report waiting for review** |
| Audit | 7. Deliverables | after 6, together with the build Phase 1 report |
| Build | 2. Analysis | draft plan in [phase2-plan.md](phase2-plan.md); 4 open questions |
| Build | 3. Website | not started |
| Build | 4. Agent and Worker | not started |

## Where things stand

**Code** (`main`): every collector, the events file and checker, and the Hugging Face
publisher. 151 offline tests pass.

**Data branch** (`origin/data`): one upcoming snapshot (2026-10-11). No history and no
followers yet.

**GitHub Actions:** no scheduled collection is on. Variables set: `HF_DATASET_REPO`.
Secrets set: `STEAM_API_KEY`, `HF_TOKEN`, `HF_DATASET_REPO`, `GP_API_KEY`.

**Raspberry Pi:**
- The history backfill is in its last stage, the hidden Early Access check (15,901 games
  at about 2 s each; 3,000 done at 4:03 pm, so done around 11:15 pm on Oct 11). It stops by itself and prints `backfill complete`.
- The follower scrape service is disabled and the pace test is stopped (Oct 11, 1:39 pm).
- The PC and the Pi share one public IP. Nothing on either machine may call
  steamcommunity.com, and nothing on the PC should send heavy store traffic while the
  Pi works.

**Followers:**
- Steam's community site blocks the IP after about 60 requests, for 8+ hours, and asking
  again while blocked seems to extend it. The old tier plan needed about 5,900 requests a day.
  It cannot work.
- The new source is the **Games Popularity API** (games-popularity.com). It reports the
  same number: median gap 0.06% on 122 games. It also gives each game's daily follower history
  back to 2024-03-15 in one request.
- Limits: about 1,000 requests a day, per key and per IP. The owner offered a whitelist in
  exchange for a backlink. A reply was drafted, asking for a key-based whitelist and whether
  their data may be republished. **No answer on republishing yet.**
- 122 follower counts from the Pi scrape sit in `C:\Users\wyc\.cache\pi\followers`
  (not committed).

**Hugging Face:** `strikeoo/steam-launch-data` is public and holds only the dataset card.
`strikeoo/steam-launch-gp` (private, for Games Popularity data) was created on Oct 11, and the
`HF_TOKEN` secret was updated (also in `.env`). Checked Oct 11: the token is fine-grained with write
access to both datasets. It also has a user-wide write scope; drop that once the publisher
stops calling `create_repo` (step 3D).

**Events:** `data/events.yaml` has 308 audited entries. The 2027 China holidays are
estimates; the weekly events check fails as a reminder around Nov 7, 2026.

## Decisions already made

- Only Steam's public endpoints, PICS and SteamSpy, plus Games Popularity for followers.
  No SteamDB scraping. No logged-in accounts.
- Wishlist rank is the main hype signal. Followers are second.
- Followers need not be fresh. Trend and history matter more, since this is not a tracking tool.
- Follower policy (900 requests a day, a setting called `GP_DAILY_BUDGET`):
  1. one pull about 8 days after each launch (whole pre-launch series plus launch week);
  2. every upcoming game with a date or a wishlist rank, once every 60 days;
  3. one player-history pull about 35 days after each launch (proposed in audit Phase 5);
  4. the rest of the budget backfills games launched since 2024-03-15, games with 10+
     reviews first (about 7 weeks with item 3), all of them in about 5 months.
- Games Popularity data stays private (a private Hugging Face dataset) until they allow
  republishing. Only derived numbers are public until then.
- The data branch is the source of truth. Hugging Face is a weekly copy rebuilt from it.
- Long one-off jobs run on the Pi. GitHub Actions only does small daily and weekly steps.
- The Steam snapshot stays daily. A missed day of release dates and ranks is lost for good.

## Next steps, in order

### 1. Land the history backfill (today)

1. Wait for `backfill complete` on the Pi.
2. Copy `history/games.csv` to the PC, check the counts, commit it to the data branch, push.
3. Nothing else runs on the Pi after that.

### 2. Audit Phase 5: research readiness (short report)

What the data can and cannot say about release-week competition, and which cheap additions
are worth it now (for example first-day and first-week review counts, and a table of
release-date changes).

### 3. Audit Phase 6: implementation (several small PRs)

**Status (2026-10-11):** A to E are built on branch `phase6-audit` (one commit per part),
215 offline tests pass. Not pushed yet. Left out on purpose:
- Trusted Publisher login: the fine-grained `HF_TOKEN` already does the job; switch later if wanted.
- The Games Popularity whitelist and republishing answer are still pending.
Workflow changes (`queue: max`, the catch-up run, the Games Popularity step) are only
checked by GitHub once pushed.

**A. Correctness fixes from the audit**
- Keep history rows when a game drops out of the listing (mark it, don't delete it).
- One failed wishlist page must not lose the whole daily snapshot.
- Retry `unavailable` review counts after a while instead of never.
- No duplicate rows in `runs.csv` when a day is rerun.
- Guard `publish_dataset --out` so it can never delete `_data`.
- Read `Retry-After` in its date form too.
- Hide `apiKey` in logs and the cache, like `key`.
- Workflow queueing (`queue: max`) and cron times off the hour.

**B. Games Popularity follower collector**
- The policy above, with a daily budget, a stop on 429, and a status per game:
  `ok`, `null`, `not_in_dataset`, `stale`.
- Store their timestamp as the observation time.
- Write to the private Hugging Face dataset.
- Credit and backlink in the README and the dataset card.
- Remove the community follower step from the daily job. Keep a repeatable comparison script.

**C. Research-readiness additions (from audit Phase 5)**
- First-day and first-week review counts for new launches (2 requests each, weekly job).
- `last_seen` column in `upcoming/apps.csv`, so a launched game's frozen row provably shows
  pre-launch tags, publisher, demo and languages.
- `first_listed` and `last_listed` in `history/games.csv` (with the "keep delisted rows" fix).
- Games Popularity player history: one pull about 35 days after each launch (about 71 a day),
  for peak players in the first week and month. Cheap if pulled on time, about 10 times dearer later.
- Dataset card: say per column whether a value was observed before launch or is today's view.

**D. Publisher hardening**
- A check before each upload: no dropped columns, tables not shrunk, required files present.
- Card date set to the newest data date.
- New tables: `runs` and `release_changes`.
- A "Data rights" section on the card.
- Login through a Trusted Publisher.

**E. Docs:** README, `docs/endpoints.md` and `scripts/server/README.md` updated to match.

### 4. Audit Phase 7 and the build Phase 1 report

One report covering what was built, verified, and still open. Then the switches go on one
at a time, checking each for a few days:
1. `COLLECT_DAILY`
2. `COLLECT_HISTORY`, once `games.csv` is on the data branch
3. the Games Popularity step
4. `PUBLISH_DATASET`, after you approve a dry-run artifact
5. `ENDPOINT_CHECK`

### 5. Build Phase 2: analysis

Starts from [phase2-plan.md](phase2-plan.md), updated first:
- Games Popularity history gives pre-launch followers for launches since 2024-03-15.
  That fills the plan's biggest gap.
- Answer its 4 open questions: niche definition, tag pairs, year-precision games,
  reviews-by-language sample.

### 6. Build Phase 3: website

A static GitHub Pages site. To decide: the URL. The spec says `wyc79.github.io/launch-window`,
but the repo is `steam-launch-window`.

### 7. Build Phase 4: agent and Cloudflare Worker

Free tier only.

## What only you can do

| When | What |
|---|---|
| now | Get Games Popularity's answer on republishing, and ask for a key-based whitelist |
| ~~before step 3B~~ | ~~Create the private dataset `strikeoo/steam-launch-gp`~~ (done Oct 11) |
| ~~before step 3D~~ | ~~Trusted Publisher or fine-grained token~~ (fine-grained token, done Oct 11) |
| after merging Phase 6 | Remove the token's user-wide write scope (the publisher no longer creates repos) |
| before the Games Popularity step | Set variables `GP_DATASET_REPO=strikeoo/steam-launch-gp` (and optionally `GP_DAILY_BUDGET`) |
| step 3D | Approve the "Data rights" wording for Steam-derived data (in the dataset card) |
| step 4 | Approve the first real upload after looking at a dry run |
| step 5 | Answer the 4 open questions in the Phase 2 plan |
| step 6 | Pick the website URL |
| around Nov 7 | Replace the 2027 China holiday estimates when the official dates are out |

## Risks to watch

- **Games Popularity is one small site** with no stated service level. If it goes away,
  followers fall back to a few manual community checks a day, and wishlist rank carries the
  hype signal alone.
- **Steam endpoints change.** The weekly endpoint check catches most of it.
- **GitHub disables scheduled workflows** in public repos after 60 days without activity.
  It is not verified whether bot commits count. GitHub emails before it happens.
- **Reviews are a stand-in for sales,** and history is today's view of the past.
  The README's Limitations section says so.
