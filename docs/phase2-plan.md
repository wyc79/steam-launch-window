# Phase 2 plan: analysis

Status: draft for review. Nothing here is built yet. Updated 2026-10-11 after the
pipeline audit: followers now come from Games Popularity, with history back to
2024-03-15, which changes sections 2 and 3.

Phase 2 turns the collected data into two things the website shows:

1. **Competition ahead:** for a tag (or tag pair), how crowded each of the next
   26 weeks is.
2. **What history says:** how past launches in that niche did, depending on
   competition and Steam events around launch.

## 1. Who counts as "in a niche"

A game is in tag T if T is among its **top 10 tags** by vote weight. Steam
shows a game's top tags first, and players vote them, so the top 10 describe
what the game is. Lower tags are often noise ("Singleplayer", "Great Soundtrack").

For a tag pair (A and B), the game needs both in its top 10.

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
| **Spread** | games with a month, quarter or year date, spread evenly over the days of their range (a "November" game adds 7/30 to each full November week) |
| **Total** | exact + spread |
| **Hype-weighted** | the same, but each game counts by its follower count (see below) |
| **No hype data** | how much of the total comes from games with no follower count and no wishlist rank |

Exact and spread are always shown separately, because a "2027" game spread
over 52 weeks is very different from 52 games with real dates.

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

`reviews_30d`: Steam-purchase reviews written in the first 30 days. A proxy for
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
  from about September 2026 on). Useful for free games, where reviews mean less.

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

For each tag (and common tag pair), split past launches into three groups by
niche competition in their launch week (quiet, normal, busy, by tercile), and
show median, 75th and 90th percentile of 30-day reviews in each group.

Hide a group with fewer than 30 games; hide the tag if any group is hidden.

## 5. Outputs for the website

Small JSON files, rebuilt by Actions:

```
site/data/tags.json                 tag id, name, games upcoming, games in history
site/data/upcoming/<tagid>.json     26 weeks x {paid, free} x {exact, spread, hype, no_hype}
                                    + top games per week
site/data/history/<tagid>.json      panel numbers from section 4, for paid and free games
site/data/pairs/<a>-<b>.json        same, for tag pairs with at least 200 past launches
site/data/events.json               events.yaml as JSON
site/data/model.json                effect sizes with intervals, sample sizes, caveats
                                    (paid model and free model)
```

Three or more tags are combined in the browser from the per-tag files (as an
approximation, labeled as such).

Refresh: upcoming files daily after the snapshot (cheap, no Steam requests);
history files and model weekly.

## 6. Tools

Python with pandas and statsmodels, in `analysis/`. Tests for the week
spreading, niche matching and event overlap logic. No Steam requests.

## 7. Questions for you

1. **Niche = top 10 tags?** Or a weight threshold (tags with at least half the
   votes of the game's top tag)?
2. **Tag pairs:** precompute only pairs with 200+ past launches (a few hundred
   files), or let the browser combine single tags for everything?
3. **Year-precision games** ("2027"): include in the spread count, or only
   show them as a separate "sometime this year" number? They are 5,858 games,
   more than all exact dates combined.
4. **Reviews by language (sample):** counting reviews by language costs one
   request per language per game. Worth doing for a 1,000-game sample, to check
   that Chinese localization really shifts who reviews? About 10,000 requests.

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
