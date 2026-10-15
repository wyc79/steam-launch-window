# Phase 3 plan: website

Status: decided (2026-10-13); steps 1 to 3 built (PR #23, PR #24, PR #25); step 4 part 1 (Competition ahead) built (PR #26); step 4 part 2 (What history says, Typical for this time of year for all games, section links, event effects in the lanes and the searchable week list) built (PR #27); section 01 Trends built (PR #28); step 5 Methods page built (PR #29); the most anticipated list in Competition ahead built (PR #30); step 6 deploy workflow built (PR #31), live since 2026-10-14.

A static site at `wyc79.github.io/steam-launch-window` that helps an indie
developer pick a launch week. It shows the numbers defined in Phase 2
(`analysis/heatmap.py`, `analysis/season.py`, `analysis/model.py`) and nothing
the data cannot back.

## Decided (2026-10-13)

- **Tools:** Vite and plain JavaScript (ES modules). No framework.
- **Sections:** each view gets its own section (below).
- **Language:** English first. Chinese comes later, so all text lives in one
  strings file from the start, and the page sets `lang`.
- **Updates:** a GitHub Actions workflow rebuilds the data files after each
  daily snapshot and redeploys GitHub Pages.
- **What the site claims:** events (sales, themed fests, Next Fest) get plain
  advice. Weekly competition is shown as a description, not a predicted
  penalty. Chinese holidays appear only as unconfirmed calendar context for
  selections that include Simplified Chinese. Caveats are one short line each;
  the reasons live on the Methods page.
- **Look:** Swiss style, loosely matching wyc79.github.io (next section).
- **Analytics:** the same Google Analytics property as wyc79.github.io, with
  the same loader: it adds Google's script with `async`, so the page never
  waits for it, and where Google is slow or blocked (mainland China) analytics
  just fail quietly. The app starts when the page is parsed
  (`DOMContentLoaded` or a module script), never on the `load` event, which a
  stuck async script can hold back.
- **Heatmap rows:** each picked tag alone, then the combination.
- **Link back:** the header carries the wyc79.github.io seal (`images/wyc.png`,
  copied over) and links to it, like that site's masthead. Those links open in
  the same tab, as do links within this site. Every other link off the site
  (Steam store pages, the data sources, GitHub, outside links on the Methods
  page) opens in a new tab, and says so to screen readers.

## Look

Taken from wyc79.github.io's `styles.css`, kept loose so this site can grow its
own pieces:

- **Type:** Inter, self-hosted (copy the woff2 files and their OFL license).
  No Google Fonts: they are blocked in mainland China and would stall the first
  paint there. Bold for headings, regular for text, tabular figures for numbers.
- **Colour:** paper `#F2F0E9`, ink `#111111`, secondary ink `#5C5A55`, soft rules
  at 18% ink, and one accent, the brand red `#A51C30`. Dark mode swaps paper and
  ink and lightens the red, following the system setting with a toggle.
- **Grid:** 12 columns (6 under 1024px, 4 under 640px), page margin
  `clamp(20px, 4vw, 72px)`, content at most 1280px wide.
- **Details:** hairline rules instead of boxes, no rounded corners, no shadows,
  small uppercase labels with letter spacing, numbered sections (01, 02...).
- **Heatmap colour:** one neutral ramp from paper to ink, so the brand red stays
  free for what matters: the selected week, the current week and focus. The
  year-only layer is hatching, not a second colour.
- **Charts:** drawn by hand in SVG. The heatmap, the bars and the event bands
  are simple shapes, and hand-drawn SVG keeps the Swiss look under full
  control. A chart library is added only if a view needs one.

## Page

One page with numbered sections, and a separate Methods page. There is no big
title: the masthead's site name is the page's `h1`, with a one-line description
and the "Patterns, not promises" note under it, so the controls sit high on the
first screen. Sections are numbered in page order (`ui/sections.js`), so the
numbers below follow from the order.

**Top bar (sticky, except on phones):** the tag picker (type to search Steam tags, picked tags as
removable chips), all of these / any of these, paid / free, languages (default English),
and the match count ("1,204 of 20,495 upcoming, 3,950 of 82,910
past launches"), which turns red when past launches are too few for the history
section ("Too few for section 02"). The count is for the picked group (paid or
free), so it agrees with the heatmap. Beside the count: links to the four sections
("01 Trends · 02 History · 03 Ahead · 04 Season", the one in view marked) and one "Raw counts"
toggle (decided 2026-10-13, as the Phase 2 plan said) that switches both the history
panel and the heatmap from "compared with a usual week" to plain counts. On phones,
where the bar does not stick, a one-line summary ("3 tags · Paid · 1,204 upcoming")
stays on top once the bar has scrolled away, with the section numbers beside it;
tapping the summary goes back and focuses the tag field.

Section order (decided 2026-10-13, Trends moved first in the review of PR #28): 01 Trends, 02
What history says, 03 Competition ahead, 04 Typical for this time of year, for all games. Reviews
in the first 30 days stand in for sales; the masthead says so, and so do What history says and
the event tooltips in Competition ahead, where reviews appear.

**01 Trends** (decided 2026-10-13; first on the page since the review of PR #28). The
selection's past launches per quarter since 2022 Q1 (where the data starts), following the
selection like What history says: tags, all / any, languages, paid or free. Launches are full
and Early Access (not leaving Early Access), with or without a 30-day review count yet (the
owner agreed), and only games still on Steam: `history.json` marks a row `listed` when the
newest listing run still lists it. The history was first listed in October 2026 and keeps a row
when Steam removes the game, so without the filter quarters from then on would keep games that
older quarters have lost, and the chart would show a rise that is not there.
- Three views, a small switch: the share of all launches (the default; the selection's
  launches over all launches of the group and languages that quarter: Steam's launches grow
  every year, so raw counts rise for almost every tag), launches per quarter, and the running
  total. Axes start at 0, and the scale comes from the full quarters: a quarter under way
  above it is cut near the top and its label says "above the scale". With no tags the share
  is 100% everywhere, so the switch leaves it out ("Pick a tag to see its share of all
  launches."); picking a tag brings it back, as the default.
- No line ahead: the chart ends at the current quarter, labelled "so far" (its days so far in
  the key, or "has just started" on its first day). Upcoming dates are too incomplete further
  out, and a niche trend from announced games waits for the calibration around 2027-01-10.
- Recent quarters: the current quarter and the two full ones before it are hatched, like the
  far weeks' "dates still being set", and marked "recent: tags may still change" (`trends.py`
  `recent`; their labels say so too): new games still carry the tags their developers set.
  The line over the chart compares 2022 with the four full quarters before the recent ones,
  with the launches behind each (Cozy, paid, English: "1.0% in 2022 (89 launches), 3.7% in
  2025 Q2 to 2026 Q1 (655)"), and only when each has at least 20 launches ("Too few launches
  to compare 2022 with recent years.").
- Bars drawn by hand in HTML, like the outlook: the quarters are a listbox (one tab stop,
  arrow keys), each labelled with its numbers ("2024 Q3: 412 of 7,350 paid launches (5.6%)"),
  and a line over the chart reads out the picked or pointed-at quarter (at first the last
  quarter before the recent ones). Phones keep all 20 quarters, with the years as the only
  labels under them. In forced colours (Windows high contrast) the bars use system colours.
- One line each: the hatched quarters, no forecast, tags are today's, removed games ("Counts
  only games still on Steam today. Games Steam removed earlier are missing, so older quarters
  look smaller and shares shift a little."), and which launches count.

**02 What history says.**
- The history panel for the selection: quiet, normal and busy launch weeks
  (normalized by default), with the median, then the 75th and 90th percentile of
  30-day reviews (low to high, decided 2026-10-13), the launches, and one line: "Reviews
  in the first 30 days, our stand-in for sales. Half of launches got the median or
  fewer." With no tags picked it speaks of all paid (or free) games.
- Launch timing, from the model's headline fit, as short lines with the size and
  its range: launching in a seasonal sale, in a themed fest that matches your tags,
  and a demo out by the end of the last Next Fest. One rule for advice (decided
  2026-10-13): a line says "Avoid ..." only when its range leaves out 1.0 and, where
  the model ran a chance test, that test agrees (p < 0.05). A range that leaves out
  1.0 without that is an "unconfirmed" line, not advice; otherwise "no clear effect"
  (or left out, for the US holidays). A group whose status is not "ok" (or no
  `model.json`) gets one line, "Not ready yet", and none of its numbers.
- Weekly competition is described, with no percentage, from the model's fit with the
  placebo, and only called "general crowding" when the placebo goes the same way as
  the launch week: "small at most; much of it is general crowding" when the launch week
  is no longer clear there, "a clear effect for free games; part of it is general
  crowding" when it is. The line says the model's niche (similar tags, a shared
  language, same price tier for paid) is not just the picked tags.
- Free games (now that their recount has landed): the same lines from the free model.
  Sales and themed fests read "no clear effect". The US holiday dips (Thanksgiving to
  Cyber Monday, Christmas to New Year) are not confirmed by the chance test, so they
  show as unconfirmed lines, with the Steam sale those weeks fall in.
- Chinese holidays only when Simplified Chinese is picked: one context line without
  numbers, never advice. Each holiday is decided on its own, from the effect for games
  with Simplified Chinese: named when that effect is clear, marked unconfirmed, with
  "from few games" (under 100) and "not confirmed by a chance test" where they apply.

**03 Competition ahead.** The heatmap for the next 13 weeks (decided
2026-10-13: beyond a quarter, announced dates say little).
- Rows: each picked tag alone, then the combination (AND or OR). Columns: weeks
  from this one, the date on top. Phones turn it sideways (weeks as rows).
- Each cell shows exact and spread dates as two visible parts (E and S on
  small screens). Normalized by default ("1.0 = as many as a typical week",
  a typical week being the row's average week of real launches over the last 52
  weeks); the shared raw counts toggle, off by default, changes only the numbers,
  not the shades. The shade follows the number as shown. Weeks more than 4 out are faded,
  labelled "dates still being set". Hover or keyboard focus on a cell shows its raw
  numbers in a small box (exact games, the spread's games' worth, the typical week);
  the cell's label carries the same text.
- Rows with under one launch in a typical week (or none) show plain counts,
  unshaded, and their row head says how few launches the year had: one launch
  more or less would swing their ratio wildly.
- Year-only dates: a hatched layer behind a toggle, off by default, and a
  "sometime in 2027: N games" line that names the row it counts (the combination).
- What past launches during an event did (decided 2026-10-13, in place of a row of its
  own): in the event block's tooltip and its week's label, never drawn in the lanes. An
  event whose line in What history says is advice gets its size ("Past paid launches during a
  seasonal sale got 37% fewer reviews."); an unconfirmed pattern, or a China holiday with
  Simplified Chinese, gets "(unconfirmed)" without a number; others nothing. Competition
  is never a number here. `src/eventeffects.js`, on `timing.js`'s rules.
- The niche trend line is built (`analysis/heatmap.py` `niche_trend`, ported, with
  `analysis/trend_calibration.py`) but held back (`SHOW_TREND` in `ui/ahead.js`): it
  flags about a fifth of tags on today's upcoming list against 4.4% on launches, so it
  waits for a calibration on snapshots against launches (about 2027-01-10).
- Events lanes under the dates, in the same week columns, with their own
  "Events" label and a rule before the heatmap rows: Steam sales, Next Fests,
  themed fests whose tags match, and Chinese holidays only when Simplified Chinese
  is among the picked languages, marked unconfirmed. Each event is a block over
  the weeks it covers, its name from its first week up to the next event in its
  lane. Rule (`src/events.js`): a themed fest shows when one of the picked tags is
  among its tags, the model's rule with the picked tags in place of a game's top 10
  (no tags picked, or a fest without tags: not shown); other holidays and releases
  are left out. On phones the events are text in each week's row. If
  `events.json` fails, the heatmap draws without the lanes and says so in one line.
- Enter or a click opens a week (arrow keys move between weeks and rows). Its header
  says what the cell counts: "2,206 games listed: 274 with exact dates · 1,932 dated
  only by month or quarter (together about 240 games' worth) · about 343 in a typical
  week", and one line that a month or quarter date is divided across the weeks it
  covers, so the cell's parts add up. The games sit in a scroll area (about 60% of the
  screen high) with a search box (case and accents aside, a live "12 of 60 games"),
  in parts, exact dates first, then month or quarter dates (and year only, with the
  year layer). Each game has its store link (new tab), date, the "moved here from October 2026,
  3 days ago" marker and the follower count when known (marked when it is an estimate
  from wishlist rank). Order inside each part: games whose top 10 tags match first,
  then the most followers (unknown last), then name, then appid. With tags picked, each
  game also says where each picked tag sits among its up to 20 tags (Steam's order; store
  pages show only the first few): "Beat 'em up: tag 6 of 20", or with several tags each
  one the game has, "Tags: Beat 'em up 6, Roguelike 12 of 20" (`tag_pos` and `tag_count`
  from `week_games`). Real text on its own line, under the date.
- Most anticipated (built): beside the week's games, the top 10 matching games of the picked
  group by Steam's Top Wishlisted rank, at any date or none, each with its store link (new
  tab), its date as the store shows it and "#212 on Top Wishlisted". A game with no date shows
  the store's own words ("Coming soon", "To be announced"; "To be announced" when the store
  gave none). No tags: "Most anticipated on Steam"; with tags: "in your niche". A for-line
  under the title names the rest, as the week list does: "All games, Paid, in Simplified
  Chinese". One caveat line: "Rank on Steam's Top Wishlisted list on <snapshot date>. Not
  wishlist counts." No threat, no advice, no follower counts or estimates. Nothing ranked
  matches: "No matching game is on Top Wishlisted." With tags picked, each game also has the
  week list's tag place line (`tag_pos` and `tag_count` from `most_anticipated`). Methods
  anchors: `#most-anticipated`, `#which-tags-match`.

**04 Typical for this time of year, for all games.** The seasonal outlook for the next 26
weeks (the all-games pattern for the picked languages, paid or free; the intro, "How busy
each coming week usually is, from past years' launches of paid games in English.", names
them): a value and its spread per week, with the events that drive it on hover
("after Next Fest October"). It stays at 26 weeks: it comes from past years, so dates
not yet set do not thin it out. China's holidays enter the pattern only when
Simplified Chinese is picked. One line under the key: "Quiet is not the same as good."

**Methods (separate page).** Built from `docs/methods.md`: sources, what each
number means, the caveats in full, and credit to Games Popularity.

## Data

The site reads static JSON from `site/public/data/` (gitignored): `vite dev` serves
it and `vite build` copies it into the build. `npm run data` in `site/` builds it
locally from a checkout of the data branch (`../_data` by default; `--gp-dir` for
follower counts) and copies the branch's `site/model.json`:

| File | Built by | When | Size (gzip) |
|---|---|---|---|
| `meta.json`, `upcoming.json`, `events.json` | `analysis.site_data` | daily | about 1 MB |
| `history.json` | `analysis.site_data` | daily (changes weekly) | about 2.8 MB |
| `model.json` | `analysis.model` | weekly, after the history run | small |

All of them load at page start (about 3.8 MB gzip): the page frame and the top
bar render first, the heatmap once `upcoming.json` and `history.json` are in. The
heatmap needs the history from the start, since its default view is normalized
by the usual week of past launches. Tags are most of `history.json` (about 1.6
MB of the 2.8), so they are the place to look if it ever needs to shrink.

The browser computes the heatmap, the outlook, the match count and the panel.
These are JavaScript ports of `heatmap.py` and `season.py`, checked against the
Python versions with shared test cases (the Python code writes expected outputs
for fixed inputs; the JavaScript tests must match them).

Two small pipeline additions (step 1, built):
- **Latest followers:** `collect_gp` also keeps `gp/latest_followers.csv` (the
  newest count per game), so the daily build does not download every day's file.
  When the file is missing, the daily job downloads every followers file once and
  the collector builds it from them (`--build-latest`; other runs never start a
  partial file). `analysis.site_data` reads it when present.
- **Model output on the data branch:** the `model` workflow runs after each
  `collect history` run (switch `MODEL_RUN=on`) and writes `site/model.json` to
  the data branch, so the daily site build reuses it instead of fitting the model
  (about 5 minutes) every day. It downloads the follower files from the public
  dataset for the follower control.
- **Free model status:** `model.json` marks the free model `ok` once at least 95%
  of the free launches the sample would include, with or without a count, are
  recounted (`reviews_purchase=all` and a 30-day count, field `recounted_share`)
  and at most 80% have no reviews. Until the 95% is reached the free model is not
  fitted: `model.json` holds only its status, `unreliable`, with its caveat. A
  group whose fit fails gets status `failed` and a short `error`. The site shows
  "not ready yet" from that status, not from a constant.

## Deploy

A `site` workflow builds and deploys to GitHub Pages:
- after each `collect daily` run, after the weekly model run, and on pushes to
  `main` that touch `site/`;
- steps: check out `main` and the data branch, fetch `gp/latest_followers.csv`,
  run `analysis.site_data` into `site/public/data`, copy `model.json` there,
  `vite build`, deploy `site/dist` with `actions/deploy-pages`;
- a repository variable `DEPLOY_SITE=on`, like the other switches.

## Quality

- Keyboard: every cell, chip and toggle reachable; the heatmap moves with the
  arrow keys. Numbers are always in text or a label, never only in colour.
- Contrast at least 4.5:1 for text in both themes. Reduced motion respected.
- Works on a phone at 360px with no sideways scrolling, apart from the heatmap's
  own scroll area.
- Loads fast from mainland China: no third-party fonts, and the only
  third-party script is the async analytics loader.

## Build order

1. Pipeline additions (latest followers, weekly `model.json`), with tests. Built.
2. JavaScript ports of the reference numbers, with the shared test cases. Built: `site/src/lib/`
   (`heatmap.js`, `season.js`); `python -m analysis.golden` writes the cases to `site/test/golden/`,
   which both test suites check. `heatmap.py` gained `heatmap_rows`, `normalized`,
   `match_count` and `week_games` (a week's games).
3. Page shell, styles and the top bar. Built: `site/index.html` and `src/main.js` (the frame
   draws at once, the data files load in parallel), `src/strings.js` (all text), `src/state.js`
   (the selection the sections subscribe to), `src/ui/` (masthead, top bar, empty section
   frames, footer), `src/styles.css`, a placeholder `methods.html`. The match count turns red
   when the history panel would hide the picked group (`historyPanel(...).shown`, parts under
   `MIN_GROUP`). `src/numbers.js` computes `matchCount` and `historyPanel` once per tags,
   mode, languages and panel measure (the measure is in the selection), so paid / free costs
   nothing and the history section can read the same panel. The count is recomputed after the click
   paints, once for several quick clicks. The tag list shows each tag's upcoming games for
   the picked languages and paid / free. On phones (under 640px) the bar does not stick.
   Analytics are not loaded on localhost. The theme choice is kept under its own key
   (`slw-theme`), since wyc79.github.io writes `yc-theme` on the same origin and defaults
   it to light.
4. Sections 01 to 03. Part 1 built: Competition ahead (now section 02) and the phone summary
   bar. `src/ui/ahead.js` draws the heatmap, the events lanes and the week's games;
   `src/heatview.js` and `src/weekdetail.js` turn the numbers into text, shade steps and labels;
   `src/events.js` picks the events. The heatmap is a plain HTML grid (ARIA `grid`, arrow keys,
   Enter opens a week), not SVG: the numbers are real text in every cell, focus is native, and
   phones swap rows and columns in CSS. Shades: 8 steps from paper to ink, cut at 0.1, 0.25,
   0.5, 1, 1.5, 2 and 3 times a typical week; from 1.0 the shade turns dark, which also skips
   the greys where no text passes 4.5:1. Far weeks use lighter steps with ink text.
   `numbers.js` caches each heatmap row (a picked tag's row is reused when more tags are
   added); a week's games are computed when it opens, for the picked group. `heatmap.py` and
   `heatmap.js` `WEEKS` went from 26 to 13 (golden cases rewritten); the seasonal outlook keeps
   its own 26. Part 2 built: What history says, Typical for this time of year, the section
   links, and the niche trend line (held back). `src/ui/history.js`
   draws the history panel (the object `numbers.js` already computed for the count's red;
   text from `src/panelview.js`) as a table with hand-drawn bars, and the model's lines
   (`src/timing.js`: which lines show, the words for a rate ratio and its range, one
   rounding rule shared with `docs/methods.md`). A demo out by the last Next Fest against
   no demo is `model.json` `demo_with_fest` (added to `analysis/model.py`, from the fit's
   clustered covariance); without it the site multiplies the two effects with a cautious
   range. The raw counts toggle is in the top bar (`ui/topbar.js`) and sets the shared
   measure for What history says and Competition ahead; the section links sit beside it (an IntersectionObserver
   marks the one in view). `src/eventeffects.js` turns the model's event verdicts
   (`timing.js` `verdict`, `chinaVerdict`) into the lanes' tooltips. A cell's raw numbers
   (`heatview.js` `countsText`) go in its label and a fixed tooltip. `src/ui/season.js`
   draws the outlook as a bar from 1.0 per week with the spread across years behind it, the
   events lanes (`src/ui/lanes.js`, shared with Competition ahead) and what each week rests on
   (`src/outlookview.js`, from the parts `season.estimate` already names); the weeks are an
   ARIA listbox (one tab stop, arrow keys), drawn down the page under 1024px. Chinese holiday
   parts are named only when Simplified Chinese is picked. `numbers.js` caches the outlook
   per languages, so a tag pick never recomputes it. The niche trend is `heatmap.py`
   `niche_trend` / `trend_from`, ported to `heatmap.js` with golden cases. Trends (now
   section 01) built: `analysis/trends.py` `quarterly` (per group and quarter: the selection's launches, all
   launches, share, running totals, the partial and recent quarters), ported to `src/lib/trends.js` with
   golden cases (`site/test/golden/trends.json`); `numbers.js` caches it per tags, mode and
   languages (about 11 to 20 ms on the real history, after the paint); `src/trendview.js` makes
   the text and the scale, `src/ui/trends.js` draws it. `analysis/site_data.py` adds the
   `listed` flag to `history.json` (Trends counts only listed games).
   Most anticipated (section 03) built: up to 10 games that match the selection (the heatmap's
   own matching, at any date or none), by Top Wishlisted rank, never by followers; `heatmap.py`
   `most_anticipated`, ported to `heatmap.js` `mostAnticipated` with golden cases; `numbers.js`
   caches it per tags, mode and languages (only the ranked games, after the paint). It sits
   beside the week's games (under them below 1024px), with one caveat line: a rank, not
   wishlist counts. `followers` and `hype_src` are not in its fields. `analysis/site_data.py`
   adds `date_text` to `upcoming.json`: the store's text, only for games with no date
   (about 140 KB more, 7 KB gzipped). PR #30.
5. Methods page. Built: `docs/methods.md` is rendered at build time by a tested,
   dependency-free Markdown converter; every main section links to its stable Methods
   anchor; the reviews-by-language analysis and table are included; all chart marks keep
   system-colour shapes in Windows High Contrast, and the heatmap keeps its split at 1.0
   there; Trends caveats are two lines. PR #29.
6. The deploy workflow, then a review of the live site. Workflow built: `.github/workflows/site.yml`.
   It runs after each successful `collect daily` or `model` run on `main`, on pushes to `main`
   that change the site or its inputs (`site/`, `docs/methods.md`, `data/events.yaml`,
   `analysis/site_data.py` and the pipeline modules it uses), and by hand. A manual run from
   another branch only builds. The build fails when `site/model.json` is missing on the data
   branch (the page would quietly drop the model lines); a missing `gp/latest_followers.csv`
   only warns. It does not join the data-branch queue, since it only reads the branch. One-time
   setup: Settings > Pages > Source "GitHub Actions", then the variable `DEPLOY_SITE=on` (done
   2026-10-14, first deploy the same day). PR #31.

Each step ends in a PR reviewed by a fresh agent before merging.
