# Phase 3 plan: website

Status: decided (2026-10-13); step 1 built (PR #23); step 2 built (PR #24, waiting for review).

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
  copied over) and links to it, like that site's masthead.

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

One page with numbered sections, and a separate Methods page.

**Top bar (sticky):** the tag picker (type to search Steam tags, picked tags as
removable chips), all of these / any of these, languages (default English),
paid / free, and the match count ("1,204 of 20,495 upcoming, 3,950 of 82,910
past launches"), which turns red when past launches are too few for section 03.
The count is for the picked group (paid or free), so it agrees with the heatmap
below it.

**01 Competition ahead.** The 26-week heatmap.
- Rows: each picked tag alone, then the combination (AND or OR). Columns: weeks
  from this one. Phones turn it sideways (weeks as rows).
- Each cell shows exact and spread dates as two visible parts. Normalized by
  default ("1.0 = a usual week"); a raw counts toggle, off by default. Weeks more
  than 4 out are faded, labelled "dates still being set".
- Year-only dates: a hatched layer behind a toggle, off by default, and a
  "sometime in 2027: N games" line beside the heatmap.
- An event band above the weeks: Steam sales, Next Fests, themed fests whose
  tags match. Chinese holidays only when Simplified Chinese is among the picked
  languages, marked unconfirmed.
- Click or focus a week: its games, with the "moved here from October 2026, 3
  days ago" marker and the follower count when known (marked when it is an
  estimate from wishlist rank). Order: games whose top 10 tags match first, then
  the most followers (unknown last), then name, then appid.

**02 Typical for this time of year.** The seasonal outlook for the same 26
weeks (the all-games pattern for the picked languages, paid or free): a value
and its spread per week, with the events that drive it on hover ("after Next
Fest October").

**03 What history says.**
- The history panel for the selection: quiet, normal and busy launch weeks
  (normalized by default), with the 75th and 90th percentile of 30-day reviews
  leading and the median after it.
- Launch timing, from the model, as short lines with the size and its range:
  launching in a seasonal sale, in a themed fest that matches your tags, after
  a demo in the last Next Fest. Weekly competition: "small, mostly general
  crowding". Free games: "not ready yet" until their recount lands.

**Methods (separate page).** Built from `docs/methods.md`: sources, what each
number means, the caveats in full, and credit to Games Popularity.

## Data

The site reads static JSON from `site/data/`:

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
  run `analysis.site_data`, copy `model.json`, `vite build`, deploy with
  `actions/deploy-pages`;
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
3. Page shell, styles and the top bar.
4. Sections 01 to 03.
5. Methods page.
6. The deploy workflow, then a review of the live site.

Each step ends in a PR reviewed by a fresh agent before merging.
