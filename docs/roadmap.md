# Roadmap and status

Last updated: 2026-10-13.

Two plans have run in parallel:
- **The build plan** (Phases 0 to 4): endpoints, data pipeline, analysis, website, agent.
- **The pipeline audit** (Phases 1 to 7): audit, other data sources, costs, Hugging Face,
  research readiness, implementation, deliverables.

The audit's implementation phase is how the build plan's Phase 1 got finished. Every phase
ends with a report, and the next one starts only after a go-ahead.

| Plan | Phase | Status |
|---|---|---|
| Build | 0. Endpoint discovery | done 2026-10-10 |
| Build | 1. Data pipeline | PRs #1 to #15 merged; scheduled jobs on since 2026-10-12; reported 2026-10-12 in [pipeline-report.md](pipeline-report.md) |
| Audit | 1 to 5. Audit, sources, costs, Hugging Face, research readiness | reported 2026-10-11 |
| Audit | 6. Implementation | [PR #13](https://github.com/wyc79/steam-launch-window/pull/13) merged 2026-10-12; fixes from the first Games Popularity run in [PR #14](https://github.com/wyc79/steam-launch-window/pull/14), merged 2026-10-12 |
| Audit | 7. Deliverables | reported 2026-10-12 in [pipeline-report.md](pipeline-report.md), together with the build Phase 1 report |
| Build | 2. Analysis | built: site data and reference numbers (PR #18), the model (PR #19), free games count all reviews (PR #20), reviews by language sample (PR #21). Left: the free recount and language sample running on the Pi, then a model rerun. See [phase2-plan.md](phase2-plan.md) and [methods.md](methods.md) |
| Build | 3. Website | plan decided 2026-10-13 in [phase3-plan.md](phase3-plan.md) (PR #22); step 1 (pipeline additions) merged in PR #23; step 2 (JavaScript ports with shared test cases) merged in PR #24; step 3 (page shell, styles, top bar) merged in PR #25; step 4 part 1 (Competition ahead, the 13-week heatmap; sections reordered with history first) in review in PR #26 |
| Build | 4. Agent and Worker | not started |

## Where things stand

**Code:**
- `main`: every Steam collector, the Games Popularity collector, the events file and
  checker, the Hugging Face publisher, and the Phase 2 analysis (`analysis/`).
- Review counts use `IUserReviewsService/GetAppReviews` (Steam retires `appreviews` on
  **2026-10-22**). Paid games count reviews from Steam purchases. Free games count all
  reviews (PR #20), because almost nobody "buys" a free game on Steam.
- PR #23 (Phase 3 step 1, merged): the daily job keeps `gp/latest_followers.csv` (newest follower
  count per game); a weekly `model` workflow writes `site/model.json` to the data branch;
  the free model is fitted only once 95% of free launches are recounted, and one group's
  failure no longer loses the other's results.

**Model findings (paid games, about 67,800 launches):** launching in a seasonal sale goes
with about 37% fewer 30-day reviews; in a themed fest matching your tags, about 45% fewer;
a demo in the last Next Fest, about 71% more. Weekly competition is small and mostly general
crowding. Chinese holidays are shown only as unconfirmed context for games with Simplified
Chinese. The free model waits for the recount.

**Data branch** (`origin/data`): daily upcoming snapshots since 2026-10-11, and
`history/games.csv`: 83,128 games launched 2022-01-01 to 2026-10-10.

**Raspberry Pi (running since 2026-10-12):** `scripts/server/run_review_jobs.sh` recounts
all reviews for about 12,400 free launches, then counts reviews by language for a sample of
1,000 paid launches. Log: `~/review-jobs.log`. About 7 to 8 hours. When it ends, copy back
`games.csv`, `reviews_by_language.csv` and `language_sample_games.csv` to `_data/history/`
on the PC (steps in [scripts/server/README.md](../scripts/server/README.md), section 5).
The PC and the Pi share one public IP: no heavy Steam traffic from the PC while it runs,
and nothing on either machine may call steamcommunity.com.

**GitHub Actions switches** (repository variables):
- On: `COLLECT_DAILY`, `COLLECT_GP`, `PUBLISH_DATASET`, `ENDPOINT_CHECK`, `MODEL_RUN`
  (first run 2026-10-13 wrote `site/model.json`; the free model is not ready yet, 0 of
  12,232 free launches recounted).
- Off: `COLLECT_HISTORY`, since 2026-10-12, so the weekly history run does not race the
  Pi. Turn it back on after the copy-back.
- Other: `HF_DATASET_REPO`. Secrets: `STEAM_API_KEY`, `HF_TOKEN`, `HF_DATASET_REPO`,
  `GP_API_KEY`.
- GitHub runs schedules in UTC and can start them hours late, so the weekly publish starts
  when the history run ends, not on its own cron.

**Followers:** from the **Games Popularity API** (games-popularity.com). It reports the
same number as Steam's community page (median gap 0.06% on 122 games) and gives each game's
daily history back to 2024-03-15 in one request. Steam's community site blocks the IP after
about 60 requests, so it is not used. The owner allowed republishing on 2026-10-12, within
the limits on their page, and said free limits will be cut and a paid plan added within days.
The first two manual runs (2026-10-12) used about 1,630 requests with no 429.

**Hugging Face:** `strikeoo/steam-launch-data` (public). The weekly publish writes the
Parquet files and the card; the daily job writes Games Popularity data under `gp/`. The
private `steam-launch-gp` dataset was copied over and deleted on 2026-10-12.

**Events:** `data/events.yaml` has 308 audited entries. The 2027 China holidays are
estimates; the weekly events check fails as a reminder around Nov 7, 2026.

## Decisions already made

- Only Steam's public endpoints, plus Games Popularity for followers and players.
  No SteamDB scraping. No logged-in accounts.
- Wishlist rank is the main hype signal. Followers are second.
- Followers need not be fresh. Trend and history matter more, since this is not a tracking tool.
- Games Popularity policy (900 requests a day, setting `GP_DAILY_BUDGET`), in this order:
  1. players 35 to 60 days after each launch (first, because a missed game loses its first
     month for good);
  2. followers about 8 days after each launch (whole pre-launch series plus launch week);
  3. every upcoming game with a date or a wishlist rank, once every 60 days;
  4. the rest backfills games launched since 2024-03-15, paid games with 10+ reviews first.
- Games Popularity data is public, under `gp/` in the same dataset. The daily job keeps it
  there directly; it is not on the data branch.
- The data branch is the source of truth for Steam data. Hugging Face is a weekly copy
  rebuilt from it, plus the Games Popularity folder.
- Long one-off jobs run on the Pi. GitHub Actions only does small daily and weekly steps.
- The Steam snapshot stays daily. A missed day of release dates and ranks is lost for good.
- The website is static, at `wyc79.github.io/steam-launch-window`. The browser does the
  tag filtering; a Worker is only for the Phase 4 agent.

## Next steps, in order

1. **When the Pi finishes:** copy back the three files, commit them to the data branch,
   set `COLLECT_HISTORY` back on, rerun the model (the free model can then be fitted), and
   look at the reviews by language sample.
2. **Phase 3 steps 4 to 6** (Competition ahead is in review in PR #26): sections
   01 to 03, the Methods page, the deploy workflow.
3. **Phase 4: agent and Cloudflare Worker,** free tier only. For Chinese users, the agent
   also gets a Tencent Cloud SCF function in a mainland China region (Workers are often
   slow or blocked there; GitHub Pages works). Check the SCF billing page once when
   setting it up. Chinese text for the page comes after the English site.

Optional later, on the Pi: first-day and first-week review counts for all launches since
2022 ([scripts/server/README.md](../scripts/server/README.md), section 4).

## What only you can do

| When | What |
|---|---|
| now | Drop the token's user-wide write scope; remove the Pi backfill service (`systemctl --user disable --now steam-history-backfill`) |
| when the Pi finishes | Copy back `games.csv`, `reviews_by_language.csv`, `language_sample_games.csv` to `_data/history/` |
| within days | When Games Popularity cuts the free limits, tell me the new numbers to set `GP_DAILY_BUDGET` (or pay) |
| any time | Check the "Data rights" wording on the dataset card, with the Games Popularity credit |
| Phase 4 | Set up the Tencent SCF function (mainland region) for the agent's China endpoint |
| around Nov 7 | Replace the 2027 China holiday estimates when the official dates are out |

## Risks to watch

- **Games Popularity is one small site** with no stated service level. If it goes away,
  followers fall back to a few manual community checks a day, and wishlist rank carries the
  hype signal alone. Its free limits are about to shrink; the catch-up queues then take
  longer, and the backfill may need a paid plan or a smaller scope.
- **Steam endpoints change.** The weekly endpoint check catches most of it.
- **GitHub disables scheduled workflows** in public repos after 60 days without activity.
  It is not verified whether bot commits count. GitHub emails before it happens.
- **Reviews are a stand-in for sales,** and history is today's view of the past.
  The README's Limitations section says so.
