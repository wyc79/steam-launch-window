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
| Build | 1. Data pipeline | PRs #1 to #13 merged; backfill on the data branch; PR #14 open |
| Audit | 1 to 5. Audit, sources, costs, Hugging Face, research readiness | reported 2026-10-11 |
| Audit | 6. Implementation | [PR #13](https://github.com/wyc79/steam-launch-window/pull/13) merged 2026-10-12; fixes from the first Games Popularity run in [PR #14](https://github.com/wyc79/steam-launch-window/pull/14) |
| Audit | 7. Deliverables | after 6, together with the build Phase 1 report |
| Build | 2. Analysis | draft plan in [phase2-plan.md](phase2-plan.md); 4 open questions |
| Build | 3. Website | not started |
| Build | 4. Agent and Worker | not started |

## Where things stand

**Code:**
- `main`: every Steam collector, the Games Popularity collector, the events file and
  checker, and the Hugging Face publisher. PR #13 (merged 2026-10-12) moved review counts
  to `IUserReviewsService/GetAppReviews` (Steam retires `appreviews` on **2026-10-22**;
  same counts checked on 4 games) and added Games Popularity retries, resumable long
  histories and a dataset card that claims no data license.
- PR #14 (`gp-players-first`): fixes from the first Games Popularity run (below).
- Checked after the merge: publish dry run on GitHub (accepts `queue: max`; 83,128 history
  rows built), `pytest -m live` without the community test (5 passed, from the PC).

**Data branch** (`origin/data`): upcoming snapshots for 2026-10-11 and 10-12, and
`history/games.csv` from the Pi backfill: 83,128 games launched 2022-01-01 to 2026-10-10,
every closed 30-day window counted, 15,901 hidden Early Access checks (258 relabeled).

**GitHub Actions:** no scheduled collection is on. Variables set: `HF_DATASET_REPO`,
`GP_DATASET_REPO` (`strikeoo/steam-launch-gp`).
Secrets set: `STEAM_API_KEY`, `HF_TOKEN`, `HF_DATASET_REPO`, `GP_API_KEY`.

**First Games Popularity run** (manual, 2026-10-12, cancelled after about 730 requests):
700 games saved to the private dataset (629 ok, 48 stale, 23 no data), 71,393 follower
points. It showed three problems, fixed in PR #14: players came after about 6 days of
follower catch-up, so games past day 42 would lose their first month; a cancel killed the
collector before it saved, so the run's requests were never counted; and games launched
43 to 60 days ago never got a players pull. The 730 requests are not in `runs.csv`, so
**do not run Games Popularity again before 2026-10-13 UTC**.

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
- Limits: about 1,000 requests a day, per key and per IP. The owner offered a whitelist in
  exchange for a backlink (now in the README). **No answer on republishing yet.**
- 122 follower counts from the Pi scrape sit in `C:\Users\wyc\.cache\pi\followers`
  (not committed).

**Hugging Face:**
- `strikeoo/steam-launch-data`: public, holds only the dataset card.
- `strikeoo/steam-launch-gp`: private, for Games Popularity data, created Oct 11.
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
- Games Popularity data stays private until they allow republishing. Only derived numbers
  are public until then.
- The data branch is the source of truth. Hugging Face is a weekly copy rebuilt from it.
- Long one-off jobs run on the Pi. GitHub Actions only does small daily and weekly steps.
- The Steam snapshot stays daily. A missed day of release dates and ranks is lost for good.
- The website lives at `wyc79.github.io/steam-launch-window`.

## Next steps, in order

### 1. Done: history backfill landed, PR #13 merged (2026-10-12)

### 2. Merge PR #14, drop the token's user-wide write scope

Steam turns off `appreviews` on Oct 22. Only `main` since PR #13 uses the new endpoint;
any review job on the Pi must run that code.

### 3. Audit Phase 7 and the build Phase 1 report

One report covering what was built, verified, and still open. Then the switches go on one
at a time, checking each for a few days:
1. `COLLECT_DAILY`
2. `COLLECT_HISTORY` (`games.csv` is on the data branch)
3. `COLLECT_GP`, after PR #14 and not before 2026-10-13 UTC (the first manual run is done;
   the first days go to about 2,600 players pulls, oldest launch first)
4. `PUBLISH_DATASET`, after you approve a dry-run artifact
5. `ENDPOINT_CHECK`, once the community block has certainly lifted (it requests one
   follower page)

Optional later, on the Pi: first-day and first-week review counts for all launches since
2022 ([scripts/server/README.md](../scripts/server/README.md), section 4).

### 4. Build Phase 2: analysis

From [phase2-plan.md](phase2-plan.md). First answer its 4 open questions: niche definition,
tag pairs, year-precision games, reviews-by-language sample.

### 5. Build Phase 3: website

A static GitHub Pages site at `wyc79.github.io/steam-launch-window` (the repo name;
decided 2026-10-11, replacing the spec's `wyc79.github.io/launch-window`).

### 6. Build Phase 4: agent and Cloudflare Worker

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
| now | Get Games Popularity's answer on republishing and a key-based whitelist |
| now | Merge PR #14, then drop the token's user-wide scope; remove the Pi backfill service |
| step 2 | The public dataset card may still say `license: mit`; the next upload replaces it with `license: other` |
| step 3 | Turn the switches on one by one (`GP_DATASET_REPO` is set; `GP_DAILY_BUDGET` optional) |
| step 3 | Approve the "Data rights" wording on the dataset card and the first real upload |
| step 4 | Answer the 4 open questions in the Phase 2 plan |
| step 6 | Set up the Tencent SCF function (mainland region) for the agent's China endpoint |
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
