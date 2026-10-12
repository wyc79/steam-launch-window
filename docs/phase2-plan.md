# Phase 2 plan: analysis

Status: building (2026-10-12). All questions answered (section 7). The site data files and the reference numbers are built; the model
is next. Updated 2026-10-11 after the pipeline audit: followers now come from Games Popularity, with history back to
2024-03-15, which changes sections 2 and 3.

Phase 2 turns the collected data into two things the website shows:

1. **Competition ahead:** for a tag selection (one or more tags, AND or OR), how crowded each of the next
   26 weeks is.
2. **What history says:** how past launches in that niche did, depending on
   competition and Steam events around launch.

## 1. Who counts as "in a niche"

Decided 2026-10-12:

- **Search filter:** a game matches a tag the user types if the tag is
  **anywhere in its tags** (Steam gives up to 20; the median game has 20). Users
  often type broad tags, and a genre tag often sits below the top 10. For
  upcoming games this adds 20 to 35% to genre tags (Shooter 5,156 to 6,514) and
  more to broad ones (Pixel Graphics +63%, Indie +181%).
- **Several tags:** the user picks a mode. **All of these** (AND, a tight niche)
  or **any of these** (OR, a wide market view).
- **Match count:** as the user picks tags and the mode, the site shows how many
  games match, out of all we have, for both upcoming games and past launches
  (for example "1,204 of 20,495 upcoming, 3,950 of 83,219 past launches"), and
  warns when past launches are too few for the history panel.
- **Competing games list:** games with the tag in their top 10 come first, then
  the rest. All are counted.
- **"Moved here" marker** (decided 2026-10-12): in that list, a game whose date
  changed in the last 30 days is marked with its old date and when it changed,
  for example "moved here from October 2026, 3 days ago", so the user sees which
  competition is new to that week. A game that got its first date in that time
  (from "Coming soon") is marked "date just set". Built by comparing the daily
  snapshots (the same changes `release_changes` lists), so the first change it
  can show is from 2026-10-12. Only a new precision or date range counts; new
  wording for the same dates does not.
- **Similarity in the model** (section 3) still uses tag vote weights, so a tag
  at #18 with few votes counts for little there. The top 10 by weight is the
  game's profile for that measure.

**Language:** a game only competes with games that share a major language with
it. The user picks the languages their game supports (default: English), and
only games supporting at least one of them are counted. Of upcoming games, 96%
support English, 46% are English-only, 33% support Simplified Chinese, and
2.6% support Simplified Chinese but not English (a separate market that would
otherwise inflate English-language niches).

Check: rerun the main numbers with top 5 and top 20 and report whether conclusions change.

**Free or paid:** a game is free if Steam marks it free (`is_free`) or "Free to
Play" is among its top 10 tags (the tag catches free-to-play games that have
not set the flag yet). Everything else is "paid or not yet priced".

| Group | Upcoming | Past launches (2022 on) |
|---|---|---|
| marked free | about 4,400 (7%) | 12,649 (15%) |
| paid price shown | a few hundred (under 1%) | |
| no price yet | about 55,000 (92%) | |

Free games declare it early, while paid games set their price at launch, so
"no price yet" upcoming games are treated as paid. Once a few weeks of
snapshots exist, we check this: of the games that launch, how many were
correctly not marked free beforehand. The accuracy goes on the Methods page.

## 2. Competition ahead (26-week heatmap)

Weeks run Monday to Sunday, Pacific time, starting with the current week.

For each week and tag:

| Number | How |
|---|---|
| **Exact** | games with a day-precision date in that week |
| **Spread** | games with a month or quarter date, spread evenly over the days of their range **still ahead of the latest snapshot** (a "November" game seen on Nov 1 adds 7/30 to each full November week; a "Q4 2026" game seen on Dec 1 is spread over December only) |
| **Total** | exact + spread |
| **Hype-weighted** | the same, but each game counts by its follower count (see below) |
| **No hype data** | how much of the total comes from games with no follower count (a ranked game counts here too until the rank-to-followers curve can be fitted) |

Exact and spread are always shown separately.

**Normalized by default** (decided 2026-10-12): each week is shown compared
with a usual week of real launches for the same selection (its average over the
last 52 weeks of history). A "raw counts" toggle, off by default, shows the
plain counts instead. Steam grows every
year, so this reads better than raw counts across tags and years. Announced
dates are not launches, and the page says so: near weeks run high because some
will slip, far weeks low because many dates are not set yet. On 2026-10-12,
English-language paid shooters (39 launches in a usual week) read 1.8 this week,
2.6 in the week of October 26, and about 0.3 six months out. Once a few months of
snapshots exist, a fairer baseline compares with how full weeks the same
distance ahead usually were.

**Near weeks read high, far weeks low** (found 2026-10-12): normalized against a
usual week of real launches, all paid English games read 1.8 this week and about
0.4 thirteen weeks out. Split up, exact dates are accurate up close (1.02 this
week) but thin out with distance (0.06 by week 13, as developers set the day
late), and vague dates add a flat 0.76 to each remaining week of Q4, many of
which will slip. So the page:
- shows exact and vague dates as two visible parts of each week;
- fades weeks more than 4 weeks out, labeled "dates still being set";
- later, once enough snapshots exist, compares each week with how full weeks
  the same distance ahead usually were (about 12 weeks ahead by mid-January,
  26 by April), and says which baseline is in use.

**Typical for this time of year** (decided 2026-10-12): for every week shown,
what past launches say about that time of year, from history only
(`analysis/season.py`). Each past week's ratio is its launches over the average
week in the 13 weeks before it. Two estimates:
- calendar: the same week of the year in past years;
- events: recurring events move from year to year (the Autumn Sale moved to
  early October in 2025), so for each Next Fest, seasonal sale or holiday within
  4 weeks, the ratios at the same distance from it in past years.

They are combined, each weighted by how steady it was across years (years /
SD squared), and shown with the spread across years. A backtest predicting the
80 complete weeks of 2025 and 2026 from earlier years only (`season.backtest`;
mean absolute error, lower is better; the last column uses the all-games
pattern for the niche):

| Selection | No pattern | Calendar | Events | Combined | All-games pattern |
|---|---|---|---|---|---|
| All paid English games | 0.198 | 0.153 | 0.143 | 0.142 | 0.142 |
| Roguelike | 0.296 | 0.254 | 0.226 | 0.229 | 0.240 |
| Puzzle | 0.227 | 0.184 | 0.184 | 0.183 | 0.181 |
| Shooter | 0.247 | 0.230 | 0.249 | 0.244 | 0.223 |
| Cozy | 0.440 | 0.537 | 0.515 | 0.506 | 0.387 |
| Shooter AND roguelike | 0.447 | 0.511 | 0.547 | 0.538 | 0.428 |

A niche's own pattern is noisy, and worse than nothing for small niches. The
all-games pattern beat no pattern for every niche tried and was about as good
as or better than the niche's own pattern (roguelike was the one exception,
0.240 against 0.229). So the site shows the all-games pattern for the user's
languages, paid or free, whatever tags are picked. On 2026-10-12 it gave 1.34
for the week after Next Fest October, 0.51 for Christmas week, 0.49 for New Year
week and 1.45 for the week after Next Fest February.

Caveats: the settings (4 weeks around an event, 3 years at least) were chosen
while looking at these same test years; events that cover the same weeks
(Winter Sale and Christmas) are weighted as if separate; and each estimate rests
on 3 to 5 years.

**Date changes:** every number uses each game's date in the newest snapshot, so
a game that moves (say from "October 2026" to "May 2027") leaves its old week
and appears in the new one in the next daily build. Older dates stay in the
daily snapshots and in `release_changes`. Games that switch to "Coming soon" or
"To be announced" leave the heatmap; games that launch leave the list and join
the history weekly. Between the 2026-10-11 and 10-12 snapshots, 218 games
changed their date text or range (for example one went from "2026" to "2027").

**Spreading starts at the latest snapshot** (decided 2026-10-12). A vague date
says the game comes somewhere in its range; if it still says so today, the part
already past is ruled out. So each game's weight goes only to the days from the
newest snapshot to the end of its range, and it is recomputed every day. A
side effect: a group that never updates gets denser as its range runs out (3,106
"2026" games over 11 weeks now, over 1 week in late December). That is honest if
the dates are true, and the slip rates in "Later" correct it once measured.

**Year-only dates are a separate layer** (decided 2026-10-12). Adding a "2027"
game into the main count would look like real competition in every week, so:

- They never add into the main color (exact plus month and quarter spread).
- A faint layer in its own style (lighter second color or hatching) shows them
  per week: the year's year-only games divided by the weeks left in that year,
  counted from the latest snapshot. Nothing is drawn for time already past.
  Hover text says what it is ("about 51 games dated only '2027', spread over its
  52 weeks").
- A toggle, "Show games without a firm date", **off by default**, shows the layer.
- One number per year sits next to the heatmap ("sometime in 2027: 2,631
  games"), with the same hype weight and list of games.

On 2026-10-12 that was 3,106 games for 2026 and 2,631 for 2027, against 4,194
exact dates in the next 26 weeks. The 2026 group over its last 11 weeks is about
280 a week, more than the exact dates (about 160 a week); the hover text says
most of them will likely slip. Slip rates from `release_changes` (see "Later"
below) will shrink this layer once measured.

**Why so many games still say "2026" in October** (checked 2026-10-12): a year
date stays valid until December 31, and many developers keep it until they set a
day or announce a delay. The group is not just dead pages: 401 have a wishlist
rank (87 in the top 1,000, three in the top 100) and 1,239 have a demo.
No game on the coming-soon list shows a month, quarter or year that has already
ended, while 43,160 show "Coming soon" or "To be announced". So an expired vague
date seems to turn into "Coming soon" rather than stay on the page; the snapshots
started too late (2026-10-11) to have seen it happen. The first check comes on
November 1, when 538 "October 2026" games either get a day, move, or change
to "Coming soon"; the big one is January 1 for the 2026 group and 2,228 "Q4 2026"
games.

**Free games are a separate layer.** They compete for front-page space and
players' time, but not for purchases. Each week shows the paid count (paid or
not yet priced) as the main number and the free count next to it. A "my game
is free-to-play" switch swaps the two, so free games become the main count.

**Price tiers cannot filter this view.** Fewer than 1% of upcoming games show
a paid price, because paid games set it at launch. So the forward heatmap
cannot be split by price tier; price only enters through the history model.

Left out:
- Games whose date passed more than 30 days ago but are still "coming soon"
  (Steam has some from 2009). These are stale pages, not competition.
- DLC, demos, software (already left out by the collector).

### Hype weight

Followers are the only hype number that exists for most games. They come from
Games Popularity for every upcoming game with a date or a wishlist rank (about
20,000), pulled once every 60 days, so a value can be up to about 60 days old.

- Game with a follower count: weight = its newest count.
- Ranked but no count yet (or `null` / `not_in_dataset`): estimate followers
  from wishlist rank, using a curve fitted on games that have both.
- Neither: no weight. These show up in "No hype data" instead of being guessed.

Followers are heavily skewed (a few games have 100,000+). The page will show
hype-weighted numbers on a log-like color scale, and list the big names in
each week so one giant does not hide the rest.

### Later, once snapshots pile up

Daily snapshots let us measure how often dates slip: what share of
"November" games really launch in November, and how often exact dates move.
The published `release_changes` table already lists every change. After about
2 months of snapshots, spread weights can use these rates instead of "evenly
over the range". Not in the first version.

## 3. What history says (the model)

### Data

Games launched from 2022-01-01 until 31 days ago, from `history/games.csv`.

| Group | Treatment |
|---|---|
| `full` and `early_access` launches | in the model, with an Early Access indicator |
| `ea_exit` (left Early Access, earlier audience) | **left out**: their launch is not a first launch |
| free games | **their own model** (12,649 games is plenty). Reviews mean something different for them (many players, low review rate, no purchase), so mixing them with paid games would blur both |
| `unavailable` review data | left out, and counted in the report |

### Outcome

`reviews_30d`: reviews written in the first 30 days (paid games: Steam
purchases only; free games: all reviews, since nobody buys them). A proxy for
sales (the common rule of thumb is one review per 30 to 60 sales, but it varies
by genre and price, so we only claim "more reviews", not "more sales").

Cheaper games sell more copies, so reviews partly measure cheapness. A second
outcome, `reviews_30d x price` (a revenue proxy), answers "which week earns the
most". Both are fitted and reported; if they disagree, the page says so.

For the free-game model, only `reviews_30d` is used (price and revenue are zero).

Checks with other outcomes, where the data exists:
- `reviews_7d`: the first week only, so less affected by what happens after
  launch (launches from October 2026 on, or all launches after the optional Pi
  backfill).
- Peak players in the first week and month, from Games Popularity (launches
  from about mid-August 2026 on). Useful for free games, where reviews mean less.

39% of launches get zero reviews and a few get tens of thousands, so the model
is for counts:

- **Main:** negative binomial regression (log link).
- **Check:** hurdle model (one part for "any reviews at all", one part for
  "how many, given some"). If the two disagree, report both. This matters most
  for free games, where many launches are tiny hobby projects with no reviews.

Both models use the same predictors, minus the price ones for free games.
The site shows a free-to-play developer the free-game results.

### Predictors

| Variable | Definition |
|---|---|
| **Niche competition** | number of other launches in the same week whose top-10 tags overlap the game's (tag-weight cosine similarity at least 0.3) and that share a major language with it; also tried as "in the same primary tag" |
| **Big competitor nearby** | a `major_release` from `events.yaml` within 3 days of launch that is on Steam at launch, paid (not `free_to_play`), not an `expansion`, and not a `surprise` (shadow drops and breakouts could not be planned around); the game itself is excluded by `steam_appid`. Free-to-play and console-only releases as a separate "attention" indicator |
| **Seasonal sale** | launch time falls inside a seasonal sale window (10:00 to 10:00 Pacific, from `pipeline.events.window`); separately, launch in the 7 days before one |
| **Next Fest** | launch during Next Fest; separately, the game had a demo in the last Next Fest before launch (from demo date) |
| **Themed fest** | launch during a themed fest whose `tags` overlap the game's top 10 tags; fests without tags are not counted |
| **Genre** | indicators for the 30 most common tags |
| **Time** | launch year and month (fixed effects), day of week |
| **Price** | log of US price; under $5 indicator |
| **Price vs niche** | log(price / median price of the game's niche), so a $25 game in an $8 niche differs from one in a $30 niche |
| **Same-tier competition** | as niche competition, but only launches in the same price tier (under $10, $10 to $25, over $25); kept instead of plain competition if it predicts held-out launches better. History only, since upcoming games rarely have prices |
| **Languages** | supports Simplified Chinese, Japanese, Russian, Korean, Brazilian Portuguese, German, French, Spanish (indicators); number of languages; English audio |
| **Regional holidays** | launch during China's Spring Festival or National Day holiday, US Thanksgiving to Cyber Monday, or Christmas to New Year (from `events.yaml`); the Chinese holidays also as interactions with Simplified Chinese support |
| **Launch hour** | hour of release in Pacific time (10 am Pacific is 1 am in China); in bands |
| **Early Access** | launch_type = early_access |
| **Demo** | had a demo before launch |
| **Publisher reach** | publisher's number of earlier releases in the data; part of a franchise |
| **Pre-launch followers** | log(1 + followers) 7 days before launch, from Games Popularity history; launches from 2024-06 on (see the caveat below) |

### The big caveat: hype

The biggest driver of launch reviews is pre-launch hype (wishlists). Wishlist
counts are never public, and wishlist rank only exists from October 2026. But
Games Popularity has daily follower history back to 2024-03-15, so launches
from about mid-2024 have **pre-launch followers**. Hype also drives date choice:
big games pick their weeks, and small games avoid them. So the competition
effect is **observational and confounded**.

What we do about it:
- **Main sample: launches from 2024-06 on,** with log followers 7 days before
  launch as a control. The 2022 to mid-2024 launches, without it, are a check.
- Report the competition effect with and without the follower control. How much
  it shrinks shows how much of it was hype.
- Control for what else we can see: price, publisher reach, franchise, Early Access, demo.
- Report the results again for "small games only" (under $20, no franchise,
  publisher with at most 2 earlier releases), where strategic date choice is weaker.
- Placebo check: competition in an unrelated week (for example 8 weeks after
  launch) should show no effect.
- Use robust standard errors clustered by launch week.
- Word every result as "launches in busier weeks got X% fewer reviews on
  average, after adjusting for ...", never "busy weeks cause X% fewer reviews".

**Tags are today's view.** Tags keep being voted after launch, so a niche built
from today's tags uses some post-launch information. For launches from October
2026 on, use the frozen pre-launch row in `upcoming/apps.csv` (`last_seen`
before launch). For older launches, the top 5 / top 20 check in section 1 shows
whether this matters.

### What gets reported

- Effects as rate ratios with 95% intervals ("one more same-niche launch that
  week goes with 2% fewer reviews, 95% CI 1% to 3%").
- Model fit against a baseline with only genre, year and price, on 2026 launches
  held out from fitting.
- A short Methods section in plain language (it becomes the Phase 3 Methods page).

## 4. Historical panel per niche

For the user's tag selection (any tags, AND or OR), split past launches into
three groups by how busy their launch week was (quiet, normal, busy, by
tercile), and show median, 75th and 90th percentile of 30-day reviews in each
group. Launches with the same busy count stay in one group; each cut is placed
as close to a third as it can be (`analysis.heatmap.cut_points`).

"Busy" uses the heatmap's rule (decided 2026-10-12): the number of other past
launches in the same week that match the user's selection. The browser counts it
from `history.json`, so the panel and the heatmap tell one story. The model
(section 3) keeps its own tag-weight similarity measure.

**Normalized busy, the default** (decided 2026-10-12; the heatmap's "raw counts"
toggle switches both): the **other** launches that week divided by the average
week in the **13 weeks before it** (an average under 1 counts as 1, so a lone
launch in a small niche reads as quiet, not busy). Only the past is used, since that is what a developer
could know when picking the date; it also matches the heatmap, whose baseline
is past launches. Launches in the data's first 13 weeks (January to March 2022)
have no baseline and are left out of the normalized panel.

Why: raw counts put mostly recent launches in the busy group (shooters: 40% of
the busy group from 2026, 5% of the quiet group). Normalized, the mix evens out
(2026 share: quiet 14%, normal 22%, busy 25%). A centered window (13 weeks
before and after) gave a similar split but uses weeks the developer could not
see. In a fast-growing niche the past lags, so its weeks read a little high;
the panel ranks weeks in thirds, so a niche-wide lean like that mostly cancels.

Hide a group with fewer than 30 games; hide the panel if any group is hidden
(the match count warns about this, section 1).

## 5. Outputs for the website

Static files on GitHub Pages, rebuilt by Actions (decided 2026-10-12). The
browser does the tag filtering and counting; Actions does the heavy parts.

```
site/data/meta.json         snapshot date, tags (id, name, games upcoming, games in
                            history), languages (the rows below point into these
                            lists), and the fitted rank-to-followers curve if any
site/data/upcoming.json     one row per upcoming game with a date or wishlist rank:
                            appid, name, date range and precision, tag ids by weight,
                            languages, free flag, hype weight, and for a date change
                            in the last 30 days the old date text and the change date
site/data/history.json      one row per past launch (not `ea_exit`): appid, launch
                            date and type, tag ids by weight, languages, free flag,
                            price, 30-day reviews
site/data/events.json       events.yaml as JSON
site/data/model.json        effect sizes with intervals, sample sizes, caveats
                            (paid model and free model)
```

Built from 2026-10-12 data by `analysis/site_data.py`: `upcoming.json` 1.0 MB
gzipped (20,481 games), `history.json` 2.8 MB (82,910 launches), the rest under
0.1 MB. The history file loads only
when the history panel opens. From these the browser builds the heatmap, the
"sometime in <year>" numbers, the match count and the history panel for any
tag combination.

Why not the Worker: filtering 83k games takes milliseconds in the browser and
the files load once. GitHub Pages works from mainland China, while Workers are
often slow or blocked there. On the free plan a Worker gets 10 ms of CPU per
request, and D1's 5 million row reads a day would cover only about 60 full
scans of the past launches (both checked 2026-10-12). The Worker stays for the
agent (Phase 4), reading the same files.

Refresh: `upcoming.json` daily after the snapshot (no Steam requests);
`history.json` and the model weekly.

## 6. Tools

Python in `analysis/`: `site_data.py` builds the files (standard library only),
`heatmap.py` defines the site's numbers as a reference with tests, which the
browser code will be checked against. The model adds pandas and statsmodels. No
Steam requests.

## 7. Questions for you

1. ~~**Niche = top 10 tags?**~~ Decided: filter on all tags, AND or OR mode
   chosen by the user (section 1).
2. ~~**Tag pairs:**~~ Decided: no pair files. The site gets per-game files and
   counts any AND/OR combination exactly in the browser (section 5). Narrow AND
   combinations will often hide history groups (under 30 games); the match
   count warns about that.
3. ~~**Year-precision games:**~~ Decided: kept out of the main color; shown as a
   faint separate layer that can be switched off, plus a "sometime in <year>"
   number (section 2).
4. ~~**Reviews by language (sample):**~~ Decided: yes. About 1,000 past
   launches, first-month reviews per language (about 10,000 Steam requests), run
   once on the Pi. First check on one game that the review endpoint accepts a
   language filter. Used to check whether Chinese localization raises reviews
   more than sales.

5. ~~**Busy compared with what?**~~ Decided: normalized by default on the
   heatmap (section 2) and the panel (section 4); a "raw counts" toggle, off by
   default, shows plain counts.
   Found while building: counted raw, "busy" mostly meant "recent"
   (English-language paid shooters averaged 23.7 other shooter launches a week
   in 2022 and 41.1 in 2026).

## Known data limits that feed into this

- History shows today's price, demo, tags and Early Access state, not launch-day
  state. For launches from October 2026 on, the snapshots and the frozen
  `upcoming/apps.csv` row give the pre-launch state.
- Hidden Early Access is only checked for games with 50+ reviews (~1.5%
  slip through below that).
- Games delisted before collection started are missing, so older years look a
  bit better than they were. Rows of games delisted later are kept.
- Follower history starts 2024-03-15. Some small games have stale or missing
  series (status `stale`, `null`, `not_in_dataset`). The backfill of past
  launches takes weeks to months at about 900 requests a day. Wishlist rank only
  covers the top ~5,300, from October 2026.
- Upcoming games almost never have a price, so price only enters through history.
- "Not marked free" before launch is assumed to mean paid; how often that is
  right is only known after a few weeks of snapshots.
- About 3% of games list "extra" languages that Steam numbers separately; they
  are kept as `extraN` because their names are not verified.
