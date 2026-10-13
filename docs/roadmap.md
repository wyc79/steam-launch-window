# Roadmap and status

Last updated: 2026-10-12.

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
| Build | 1. Data pipeline | PRs #1 to #15 merged; scheduled jobs on since 2026-10-12; reported 2026-10-12 in [pipeline-report.md](pipeline-report.md) |
| Audit | 1 to 5. Audit, sources, costs, Hugging Face, research readiness | reported 2026-10-11 |
| Audit | 6. Implementation | [PR #13](https://github.com/wyc79/steam-launch-window/pull/13) merged 2026-10-12; fixes from the first Games Popularity run in [PR #14](https://github.com/wyc79/steam-launch-window/pull/14), merged 2026-10-12 |
| Audit | 7. Deliverables | reported 2026-10-12 in [pipeline-report.md](pipeline-report.md), together with the build Phase 1 report |
| Build | 2. Analysis | in progress: site data files and reference numbers built (PR #18); the model built (PR #19, not merged): busy weeks go with about 1% fewer reviews per same-niche launch, but a placebo 8 weeks later is as large (the launch week keeps a small effect at the edge of noise); Chinese holidays are calendar context only; free model unreliable until free reviews are recounted; see [phase2-plan.md](phase2-plan.md) and [methods.md](methods.md) |
| Build | 3. Website | plan decided 2026-10-13 in [phase3-plan.md](phase3-plan.md); step 1 (pipeline additions: `gp/latest_followers.csv`, weekly `site/model.json`, free model status from the data) built, PR open |
| Build | 4. Agent and Worker | not started |

## Where things stand

**Code:**
- `main`: every Steam collector, the Games Popularity collector, the events file and
  checker, and the Hugging Face publisher. PR #13 (merged 2026-10-12) moved review counts
  to `IUserReviewsService/GetAppReviews` (Steam retires `appreviews` on **2026-10-22**;
  same counts checked on 4 games) and added Games Popularity retries, resumable long
  histories and a dataset card that claims no data license.
- PR #14 (merged 2026-10-12): fixes from the first Games Popularity run (below).
- PR #15 (merged 2026-10-12): Games Popularity data moves from the private dataset to `gp/` in
  the public one (the owner allowed republishing on 2026-10-12), and the weekly publish
  now starts when the history run ends instead of on its own cron.
- Checked after the merge: publish dry run on GitHub (accepts `queue: max`; 83,128 history
  rows built), `pytest -m live` without the community test (5 passed, from the PC).

**Data branch** (`origin/data`): upcoming snapshots for 2026-10-11 and 10-12, and
`history/games.csv` from the Pi backfill: 83,128 games launched 2022-01-01 to 2026-10-10,
every closed 30-day window counted, 15,901 hidden Early Access checks (258 relabeled).

**GitHub Actions:** on since 2026-10-12 (about 05:35 UTC): `COLLECT_DAILY`, `COLLECT_GP`,
`COLLECT_HISTORY`, `PUBLISH_DATASET`. Not on: `ENDPOINT_CHECK`. Other variable:
`HF_DATASET_REPO` (`GP_DATASET_REPO` is not used after PR #15 and can be deleted).
GitHub runs schedules in UTC and can start them late: the first weekly history run (due
Monday 06:17 UTC) started at 15:26 UTC. It found nothing to do, because a manual run at
07:09 UTC had done the work. That delay is why PR #15 starts the publish from it.
Secrets set: `STEAM_API_KEY`, `HF_TOKEN`, `HF_DATASET_REPO`, `GP_API_KEY`.

**First Games Popularity run** (manual, 2026-10-12, cancelled after about 730 requests):
700 games saved to the private dataset (629 ok, 48 stale, 23 no data), 71,393 follower
points. It showed three problems, fixed in PR #14: players came after about 6 days of
follower catch-up, so games past day 42 would lose their first month; a cancel killed the
collector before it saved, so the run's requests were never counted; and games launched
43 to 60 days ago never got a players pull. The 730 requests are not in `runs.csv`, so
another run on 2026-10-12 (UTC) thinks it has 900 left and stops at their ceiling after
about 270. With PR #14 that is a clean stop: pages already fetched are kept, the step
passes, and no other run starts that day.

**Second Games Popularity run** (manual, 2026-10-12 05:10 UTC, with PR #14): 900 requests,
748 games (601 ok, 147 stale), 287,103 points, stopped at the budget. With the first run,
that is about 1,630 requests in one UTC day and no 429, so the 1,000 a day cap was not
enforced that day.

**Raspberry Pi:**
- The history backfill finished on Oct 11 (9:22 pm) and is on the data branch. Its
  service can be removed (`systemctl --user disable --now steam-history-backfill`).
- The follower scrape service is disabled and the pace test is stopped (Oct 11, 1:39 pm).
- The PC and the Pi share one public IP. Nothing on either machine may call
  steamcommunity.com, and nothing on the PC should send heavy store traffic while the
  Pi works.

**Followers:**
- Steam's community site blocks the IP after about 60 requests, for 8+ hours, and asking
  again while blocked seems to extend it. The old tier plan needed about 5,900 requests a day.
- The new source is the **Games Popularity API** (games-popularity.com). It reports the
  same number (median gap 0.06% on 122 games) and gives each game's daily follower history
  back to 2024-03-15 in one request.
- Limits: the owner said about 1,000 requests a day, per key and per IP; their docs page
  (checked 2026-10-12) says only 1 request a second per key. The owner offered a whitelist
  in exchange for a backlink (now in the README).
- **The owner's answer (2026-10-12):** republishing is OK, within the limits on their page.
  Free limits will be cut and a paid plan added within days. When that happens, lower
  `GP_DAILY_BUDGET` to fit.
- 122 follower counts from the Pi scrape sit in `C:\Users\wyc\.cache\pi\followers`
  (not committed).

**Hugging Face:**
- `strikeoo/steam-launch-data`: public. The weekly publish writes the Parquet files and
  the card; after PR #15 the daily job writes Games Popularity data under `gp/`.
- `strikeoo/steam-launch-gp`: private, held Games Popularity data until PR #15; copied
  to `gp/` and deleted on 2026-10-12.
- `HF_TOKEN` (secret and `.env`): fine-grained, write access to both. It also has a
  user-wide write scope, which is no longer needed now that PR #13 is merged.

**Events:** `data/events.yaml` has 308 audited entries. The 2027 China holidays are
estimates; the weekly events check fails as a reminder around Nov 7, 2026.

## Decisions already made

- Only Steam's public endpoints, plus Games Popularity for followers and players.
  No SteamDB scraping. No logged-in accounts.
- Wishlist rank is the main hype signal. Followers are second.
- Followers need not be fresh. Trend and history matter more, since this is not a tracking tool.
- Games Popularity policy (900 requests a day, setting `GP_DAILY_BUDGET`), in this order:
  1. players 35 to 60 days after each launch (hourly, first month, one request until about
     day 41, then two; first,
     because a missed game loses its first month for good);
  2. followers about 8 days after each launch (whole pre-launch series plus launch week);
  3. every upcoming game with a date or a wishlist rank, once every 60 days;
  4. the rest backfills games launched since 2024-03-15, paid games with 10+ reviews first.
  The first weeks clear catch-up queues: about 5,300 recent launches and 20,000 upcoming
  games come before the backfill.
- Games Popularity data is public, under `gp/` in the same dataset (allowed 2026-10-12).
  The daily job keeps it there directly; it is not on the data branch.
- The data branch is the source of truth for Steam data. Hugging Face is a weekly copy
  rebuilt from it, plus the Games Popularity folder.
- Long one-off jobs run on the Pi. GitHub Actions only does small daily and weekly steps.
- The Steam snapshot stays daily. A missed day of release dates and ranks is lost for good.
- The website lives at `wyc79.github.io/steam-launch-window`.

## Next steps, in order

### 1. Done: history backfill landed, PR #13 merged (2026-10-12)

### 2. Done: PR #14 merged, switches on (2026-10-12)

`COLLECT_DAILY`, `COLLECT_HISTORY`, `COLLECT_GP` and `PUBLISH_DATASET` are on. Still to
do: drop the token's user-wide write scope. Steam turns off `appreviews` on Oct 22; only
`main` since PR #13 uses the new endpoint, so any review job on the Pi must run that code.

### 3. Done: Games Popularity data public (PR #15, 2026-10-12)

Merged; the private dataset's files were copied to `gp/` and checked byte for byte; the
daily job and a publish ran against the public dataset and the card lists `gp_followers`
and `gp_players`. The private dataset is deleted. Still to do: delete the `GP_DATASET_REPO` variable.

### 4. Reported: audit Phase 7 and the build Phase 1 report (2026-10-12)

[pipeline-report.md](pipeline-report.md): what was built, verified, and still open, with
costs and your checklist (section G). Waiting for your review. Keep an eye on the
scheduled jobs for the next few days (the first days of Games Popularity go to about
1,900 players pulls, oldest launch first). `ENDPOINT_CHECK` can go on now: it runs
from a GitHub runner and no longer requests a community follower page (replaced by one
Games Popularity request).

Optional later, on the Pi: first-day and first-week review counts for all launches since
2022 ([scripts/server/README.md](../scripts/server/README.md), section 4).

### 5. Build Phase 2: analysis

From [phase2-plan.md](phase2-plan.md). Its 4 questions (niche definition, tag pairs,
year-only dates, reviews by language) were answered on 2026-10-12.

### 6. Build Phase 3: website

A static GitHub Pages site at `wyc79.github.io/steam-launch-window` (the repo name;
decided 2026-10-11, replacing the spec's `wyc79.github.io/launch-window`).

### 7. Build Phase 4: agent and Cloudflare Worker

Free tier only.

**Chinese users (decided 2026-10-11):** GitHub Pages works from mainland China (tested
by the owner), so the static site needs no copy. Cloudflare Workers are often slow or
blocked there, so the agent also gets a **Tencent Cloud SCF function in a mainland China
region**, next to the Worker. The owner runs the same setup for a portfolio chat on the
free basic tier. When setting it up, check the account's billing page once: the
international docs describe a monthly base package after the first 3 months. Chinese
text for the page is a separate Phase 3 item.

## What only you can do

| When | What |
|---|---|
| now | Drop the token's user-wide scope; remove the Pi backfill service |
| now | Delete the `GP_DATASET_REPO` variable; turn on `ENDPOINT_CHECK` |
| after the Phase 3 step 1 merge | Set `MODEL_RUN=on`, then run the `model` workflow by hand once to put `site/model.json` on the data branch |
| step 3 | Check the "Data rights" wording on the dataset card, now with the Games Popularity credit |
| within days | When Games Popularity cuts the free limits, lower `GP_DAILY_BUDGET` (or pay) |
| step 7 | Set up the Tencent SCF function (mainland region) for the agent's China endpoint |
| around Nov 7 | Replace the 2027 China holiday estimates when the official dates are out |

## Risks to watch

- **Games Popularity is one small site** with no stated service level. If it goes away,
  followers fall back to a few manual community checks a day, and wishlist rank carries the
  hype signal alone. Its free limits are about to shrink (2026-10-12); the catch-up queues
  then take longer, and the backfill may need a paid plan or a smaller scope.
- **Steam endpoints change.** The weekly endpoint check catches most of it.
- **GitHub disables scheduled workflows** in public repos after 60 days without activity.
  It is not verified whether bot commits count. GitHub emails before it happens.
- **Reviews are a stand-in for sales,** and history is today's view of the past.
  The README's Limitations section says so.
