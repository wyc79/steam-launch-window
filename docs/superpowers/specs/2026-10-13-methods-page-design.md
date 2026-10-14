# Methods Page and Site Fixes Design

## Goal

Build Phase 3 step 5: a complete Methods page generated from
`docs/methods.md`, a local reviews-by-language summary, Windows High Contrast
support for every chart mark, and shorter Trends notes. The page must let a
reader trace every main-page number to its source and calculation.

## Scope and constraints

- Work on branch `site-methods`, based on `origin/main`, in an isolated
  worktree.
- Keep Vite and plain JavaScript. Add no runtime dependency.
- Do not call Steam, Games Popularity, or Hugging Face.
- Treat `_data` as read-only.
- Put UI text in `site/src/strings.js` or `docs/methods.md`.
- Keep text short, plain, and free of em dashes.
- Use the repository `.venv` for Python.
- Preserve the existing Swiss layout, light and dark themes, and masthead.
- Open a pull request and wait for CI. Do not merge it.

## Build-time Methods rendering

The Methods page will use a small local Markdown renderer in
`site/build/methods-markdown.js`. It will support only the syntax used by
`docs/methods.md`: headings, paragraphs, ordered and unordered lists, tables,
links, bold text, and inline code.

The renderer will escape source text and attribute values before adding markup.
Links will accept local fragments and safe web URLs. Unsafe URL schemes will
not become links. Headings will receive deterministic slugs, with numeric
suffixes for duplicates. The four section anchors are:

- `trends`
- `what-history-says`
- `competition-ahead`
- `typical-for-this-time-of-year`

`site/vite.config.js` will read `docs/methods.md` and expose the rendered HTML
through a virtual module during development and production builds. The browser
will receive generated HTML and will not parse Markdown. The renderer will be
exported for direct unit tests.

`site/src/methods.js` will import the generated article, place it inside the
existing masthead and footer shell, and keep the existing theme behavior. The
article will include a short table of contents written in the Markdown source.
Methods-specific CSS will preserve the site's grid and type rules. Tables will
either fit or scroll inside their own wrapper at 360 pixels, never the whole
page.

## Methods content

`docs/methods.md` remains the single source of truth. It will be reorganized for
a general reader in the main page's order:

1. Trends
2. What history says
3. Competition ahead
4. Typical for this time of year

The page will also cover sources, the review-count outcome, the model, the
advice rule, the placebo, Chinese holidays, the held-back niche trend, language
shares, and limits.

The source section will credit Steam's public endpoints, Games Popularity, and
the public `strikeoo/steam-launch-data` dataset. It will link to Games
Popularity and state that its owner allowed republication on 2026-10-12.

Paid games use Steam-purchase reviews from the first 30 days. Free games use all
reviews from the first 30 days. Reviews are a stand-in for sales, not sales.

A model line becomes advice only when its 95% interval excludes 1.0 and its
chance test, when present, has `p < 0.05`. Other results are described as
unconfirmed or as having no clear effect.

Weekly competition is descriptive. The eight-week placebo is about as strong
as the launch-week association, so the chart does not claim a predicted loss.
Chinese holidays stay unconfirmed context because there are few windows and
all overlap another Steam event.

The niche trend stays hidden until a daily-snapshot versus launch calibration
is possible around 2027-01-10. Trends count only games still listed on Steam.
Recent-quarter tags can change, while old quarters omit games removed before
collection began.

The limits section will say that reviews are not sales, history is today's view
of past games, and announced launch dates move.

Every model value will be checked against `origin/data:site/model.json` and the
local data. Any corrected value will be named in the pull request.

## Reviews by language

`analysis/languages.py` will use the Python standard library and local CSV
files. It will expose pure calculation functions plus a command-line entry
point. For each Simplified Chinese support group it will calculate:

- pooled share: the sum of a language's reviews divided by the sum of the
  group's `all` reviews;
- median per-game share: each game's language reviews divided by its `all`
  reviews, followed by the median across games;
- other languages: `all` reviews minus the ten named language counts.

Rows will be joined to `language_sample_games.csv`, so only the saved 1,000-game
sample is included. Input validation will reject duplicate app, language pairs,
missing `all` rows, mismatched support flags, negative counts, and language
counts larger than `all` for a game. Tests will use small hand-calculated
fixtures before the full local files are checked against the expected headline
values.

The Methods page will include a compact results table and three one-line
caveats: selection is not a treatment effect, pooled results are shaped by big
games, and Latin American Spanish and European Portuguese were not counted.
It will also explain Steam's `koreana` name.

## Main-page links and Trends notes

Each section introduction will receive a small “How this is measured” link to
its Methods anchor. The text will live in `site/src/strings.js`. Tests will
assert the href for each section so heading or navigation changes cannot break
the connection silently.

The Trends notes will become two paragraphs:

1. The first describes hatching and the current quarter. It will keep the
   data-derived day count and use “has just started” on the first day.
2. The second states that the chart counts full and Early Access launches still
   on Steam with today's tags, and that no forecast is shown because future
   dates are incomplete.

The longer details will move to the Methods page.

## Forced colors

The existing Trends pattern will extend to every background-only mark. Inside
`@media (forced-colors: active)`, marks will opt out with
`forced-color-adjust: none` and use `CanvasText`, `Canvas`, and `Highlight`.
Hatching will distinguish recent, year-only, or other special states.

Coverage includes heatmap parts, year-only parts, event blocks and phone event
tags, history percentile bars and median ticks, outlook spread boxes and bars,
phone outlook event tags, and Trends bars. Visible numbers will keep a system
color with sufficient contrast against the mark behind them.

`site/test/contrast.test.js` will assert the forced-colors rules by semantic
chart part, following the current Trends checks.

## Testing and verification

Implementation will follow test-driven development. New renderer behavior,
language calculations, section links, Trends wording, and forced-colors rules
will first receive failing tests.

Final automated checks:

- `npm test` in `site/`
- `npm run build` in `site/`
- `.venv/Scripts/python -m pytest -q -m "not live"`
- local site data built with `npm run data -- --data-dir <repo>/_data`

Visual checks will run against `vite preview` on a port other than 4173. Each
run will use a fresh headless Chrome profile with non-localhost requests
blocked. Screenshots will cover the main and Methods pages at 1280 and 360
pixels in light, dark, and forced-colors modes. The checks will also cover
keyboard operation, 4.5:1 text contrast, page-level horizontal overflow, and
all four Methods links.

## Documentation and delivery

`docs/phase3-plan.md` will mark step 5 built. `docs/roadmap.md` will update the
Phase 3 row and next steps. Commits will use the required co-author trailer.
The pull request body will summarize the implementation, tests, language
results, corrected Methods values, screenshots, and any check that could not be
completed. It will end with the required Claude Code attribution.
