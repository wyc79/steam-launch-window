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
| Build | 1. Data pipeline | PRs #1 to #12 merged; PR #13 open; backfill finishing |
| Audit | 1 to 5. Audit, sources, costs, Hugging Face, research readiness | reported 2026-10-11 |
| Audit | 6. Implementation | [PR #13](https://github.com/wyc79/steam-launch-window/pull/13): reviewed, CI green; merge after the backfill lands |
| Audit | 7. Deliverables | after 6, together with the build Phase 1 report |
| Build | 2. Analysis | draft plan in [phase2-plan.md](phase2-plan.md); 4 open questions |
| Build | 3. Website | not started |
| Build | 4. Agent and Worker | not started |

## Where things stand

**Code:**
- `main`: every Steam collector, the events file and checker, and the Hugging Face publisher.
- PR #13 (`phase6-audit`): the Games Popularity collector, the data-safety fixes from the
  audit, publisher checks, docs. A fresh reviewer agent reviewed it; its fixes are in.
  A second review (2026-10-11) added: review counts from `IUserReviewsService/GetAppReviews`
  (Steam retires `appreviews` on **2026-10-22**; same counts checked on 4 games), retries
  for Games Popularity pulls that got nothing, resumable long histories, no `mit` license
  on the dataset card. 250 offline tests pass.

**Data branch** (`origin/data`): one upcoming snapshot (2026-10-11). No history and no
followers yet.

**GitHub Actions:** no scheduled collection is on. Variables set: `HF_DATASET_REPO`.
Secrets set: `STEAM_API_KEY`, `HF_TOKEN`, `HF_DATASET_REPO`, `GP_API_KEY`.

**Raspberry Pi:**
- The history backfill is in its last stage, the hidden Early Access check (15,901 games
  at about 2 s each; done around 11:15 pm on Oct 11). It prints `backfill complete`.
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
  user-wide write scope, which is no longer needed once PR #13 is merged.

**Events:** `data/events.yaml` has 308 audited entries. The 2027 China holidays are
estimates; the weekly events check fails as a reminder around Nov 7, 2026.

## Decisions already made

- Only Steam's public endpoints, plus Games Popularity for followers and players.
  No SteamDB scraping. No logged-in accounts.
- Wishlist rank is the main hype signal. Followers are second.
- Followers need not be fresh. Trend and history matter more, since this is not a tracking tool.
- Games Popularity policy (900 requests a day, setting `GP_DAILY_BUDGET`), in this order:
  1. players 35 to 42 days after each launch (hourly, first month, one request; first,
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

### 1. Land the history backfill (tonight)

1. Wait for `backfill complete` on the Pi.
2. Copy `history/games.csv` to the PC, check the counts, commit it to the data branch, push.

### 2. Merge PR #13 (before 2026-10-22)

Steam turns off `appreviews` on Oct 22. After that, only code with the PR's
`GetAppReviews` change can collect review counts. Any review job on the Pi still
running then must be stopped, updated and restarted.

1. Optional, before merging: run **publish dataset** by hand on the `phase6-audit` branch
   without "upload" (a dry run: no Steam requests, nothing uploaded). It confirms GitHub
   accepts the new `concurrency.queue: max` setting.
2. Merge.
3. Drop the token's user-wide write scope.

### 3. Audit Phase 7 and the build Phase 1 report

One report covering what was built, verified, and still open. Then the switches go on one
at a time, checking each for a few days:
1. `COLLECT_DAILY`
2. `COLLECT_HISTORY`, once `games.csv` is on the data branch
3. `COLLECT_GP`, with `GP_DATASET_REPO=strikeoo/steam-launch-gp`; first one manual run
   with "Games Popularity" ticked, then a look at the private dataset
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
| tonight | Copy and commit the finished `games.csv` |
| before Oct 22 | Merge PR #13 (review counts break on old code after Oct 22), then drop the token's user-wide scope |
| step 2 | The public dataset card may still say `license: mit`; the next upload replaces it with `license: other` |
| step 3 | Set `GP_DATASET_REPO` (and optionally `GP_DAILY_BUDGET`), then the switches one by one |
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
