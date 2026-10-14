# Methods

Steam Launch Window helps an indie developer compare possible launch weeks.
It shows patterns in public data, not promises about what a game will sell.
The model numbers below come from the 2026-10-13 run.

## On this page

- [Sources](#sources)
- [Trends](#trends)
- [What history says](#what-history-says)
- [Competition ahead](#competition-ahead)
- [Typical for this time of year](#typical-for-this-time-of-year)
- [Reviews by language](#reviews-by-language)
- [Limits](#limits)

## Sources

- **Steam:** public `IStoreQueryService/Query`,
  `IStoreBrowseService/GetItems`, `IStoreService/GetTagList`, and
  `IUserReviewsService/GetAppReviews` endpoints provide games, release dates,
  tags, prices, demos, languages, and reviews. The collector also reads Steam's
  store search for the Top Wishlisted rank. The rank decides which undated
  games get a Games Popularity follower lookup, and gives an estimated follower
  count to a ranked coming-soon game that has none.
- **[Games Popularity](https://games-popularity.com/):** follower and player
  counts. Games Popularity's owner gave permission to republish these counts on
  2026-10-12. The site credits the source wherever it uses them.
- **[strikeoo/steam-launch-data](https://huggingface.co/datasets/strikeoo/steam-launch-data):**
  the public Hugging Face copy of the collected launch, snapshot, event, review,
  and Games Popularity data.

The site reads static files built from these sources. It does not call them in
the browser.

## Trends

The Trends chart counts the selected games in each quarter from 2022 Q1 to the
current quarter. A selection includes full and Early Access launches. It does
not include a game leaving Early Access, because that is not its first launch.
Unlike [What history says](#what-history-says), Trends also counts launches that
do not have 30 days of reviews yet. Tags, all or any matching, languages, and
paid or free work the same way as in the other sections.

The three views use the same quarterly counts:

- **Share of all launches:** selected launches divided by all launches in the
  same paid or free group and selected languages that quarter. This is the
  default because Steam's total launch count grows over time.
- **Per quarter:** the selected launch count.
- **Cumulative:** the running selected launch count since 2022 Q1.

The current quarter ends at the newest complete data day. The page calculates
the number of elapsed days and the quarter's total days. On its first day it
says the quarter has just started. The chart does not extend into future
quarters because announced dates are too incomplete.

The chart counts only games that Steam still lists in the newest history run.
Collection started in October 2026. Games removed before then are missing, so
older quarters are smaller than they were at the time. Once collection began,
a removed game's row stayed in the history with an old `last_listed` date, so
the `listed` flag can exclude it from every quarter consistently.

Tags are today's Steam tags. Player votes can reshape a new game's tags, so the
current quarter and the two full quarters before it are hatched. The comparison
line uses 2022 and the four full quarters before those recent quarters. It is
shown only when each side has at least 20 selected launches.

## What history says

This section has two different summaries: the history panel and the timing
model.

### Quiet, normal, and busy weeks

The history panel filters past full and Early Access launches by the current
selection. Paid and free games are kept apart. A week runs Monday to Sunday in
Pacific time.

By default, a week's competition is its matching launches, excluding the game
itself, divided by the average matching launches in the previous 13 weeks.
Raw-count mode uses the matching launch count without that division. Games are
split into quiet, normal, and busy thirds. Equal competition values stay
together, so the groups need not be exactly the same size.

Each group shows its games and the median, 75th percentile, and 90th percentile
of first-30-day reviews. A group needs at least 30 games. Half the launches got
the median or fewer reviews.

### Reviews stand in for sales

For paid games, the outcome is reviews from Steam purchases in the first 30
days. For free games, it is all reviews in the first 30 days because almost
nobody purchases a free game. Reviews stand in for sales, but the reviews per
sale vary by genre and price. The site therefore says reviews, not sales.

The model starts with every Steam launch from 2022-01-01 through 2026-09-11,
31 days before the data date. That is 80,403 launches. It leaves out 541 games
leaving Early Access and 10 launches whose week begins before the analysis
window, keeping 79,852 first launches. The paid model fits 67,791 games after
leaving out 72 paid games without a usable price. The free model fits 11,989
games. A game is free when Steam marks it free or Free to Play is among its top
10 tags.

### The timing model

The model asks whether games in busier weeks, sales, or fests got different
review counts than otherwise similar launches. Paid and free games are fitted
separately with a negative binomial regression. This model suits counts that
are often zero and sometimes very large. Among paid launches, 24.7% received no
review in 30 days.

Each result is a rate ratio. A ratio of 0.90 means 10% fewer reviews on average;
1.20 means 20% more. The 95% interval shows uncertainty. Launches in the same
week share news cycles and store traffic, so the uncertainty calculation groups
them by launch week.

The model adjusts for:

- other launches that week in a similar niche, with a shared major language
  and, for paid games, the same price tier;
- sales, the seven days before a sale, Next Fest, matching themed fests, a demo
  by the last Next Fest, big releases within three days, and holidays;
- price, the niche's usual price, Early Access, demo, franchise, the
  publisher's earlier launches, languages, English audio, common tags, and
  launch hour;
- year, month, and day of week.

Two games share a niche when their top 10 tags, weighted by player tag votes,
have cosine similarity of at least 0.3.

### When a pattern becomes advice

A line becomes advice only when its 95% interval excludes 1.0 and its chance
test, when one was run, has `p < 0.05`. A range that excludes 1.0 but fails that
second test is unconfirmed. A range that includes 1.0 has no clear effect.

The chance test is for events that occurred only a few times. It removes the
event from the main model, places fake windows of the same length on random
weeks 1,000 times, and measures how often a fake result is at least as far from
1.0 as the real result. It preserves weekday and Pacific time and does not put a
fake window on a real window of that event. A check on 15 fake sets for two
events agreed with full refits at a correlation above 0.99.

There are 4 to 19 sale, fest, and holiday windows, plus 69 themed fests. For
paid games, sales (`p = 0.001`) and themed fests (`p = 0.04`) pass. Next Fest,
Thanksgiving, and Christmas do not. Chinese holidays are the exception: National
Day passes (`p = 0.007`) and Spring Festival does not (`p = 0.08`), but both
overlap other events and have only 4 or 5 windows, so neither becomes advice.
See [Chinese holidays](#chinese-holidays). For free games, no event passes:
sales give `p = 0.55` and themed fests `p = 0.96`.

### Paid games

| Launch condition | Reviews against otherwise similar launches | Chance test | Games |
|---|---|---|---:|
| 10 more launches in the same niche and price tier that week | 9% fewer, from 6% to 11% fewer | | 67,791, median 15 competitors |
| During a seasonal sale | 37% fewer, from 24% to 47% fewer | ratio 0.75; `p = 0.001`, 19 sales | 5,310 |
| In the 7 days before a sale | no clear effect, from 32% fewer to 6% more | | 5,337 |
| During Next Fest | no clear effect, from 19% fewer to 75% more | ratio 1.13; `p = 0.34`, 14 fests | 3,047 |
| Demo out by the end of the last Next Fest, against a later demo | 71% more, from 36% to 115% more | | 10,394 |
| During a themed fest for one of its tags | 45% fewer, from 35% to 54% fewer | ratio 0.56; `p = 0.04`, 69 fests | 1,008 |
| Within 3 days of a big paid release | no clear effect, from 11% fewer to 18% more | | 21,375 |
| Spring Festival, without Simplified Chinese | unconfirmed: 37% fewer, from 14% to 54% fewer | ratio 0.70; `p = 0.08`, 5 holidays pooled | 877 |
| Spring Festival, with Simplified Chinese | unconfirmed: 29% fewer, from 8% to 46% fewer | same pooled test | 531 |
| National Day, without Simplified Chinese | context only: 56% fewer, from 33% to 71% fewer | ratio 0.51; `p = 0.007`, 4 holidays pooled | 698 |
| National Day, with Simplified Chinese | context only: 52% fewer, from 6% to 76% fewer | same pooled test | 349 |
| Thanksgiving through Cyber Monday | no clear effect, from 25% fewer to 154% more | ratio 1.26; `p = 0.42`, 4 holidays | 713 |
| Christmas through New Year | no clear effect, from 23% fewer to 73% more | ratio 1.11; `p = 0.61`, 4 holidays | 741 |
| Early Access | 18% more, from 0.2% to 38% more | | 10,962 |

Percentages come from rate ratios in `model.json` and use round-half-up to whole
percents. The reviews times price revenue proxy gives the same broad picture.

The model has two demo terms. A demo released after the last Next Fest went with
40% fewer reviews, from 28% to 51% fewer, than no demo. Multiplying that by the
last-Next-Fest term gives about the same review count as no demo, with a ratio of
1.02. The current site uses a cautious combined interval because the model file
does not yet carry the covariance-based combined range.

At the same niche price, a game priced twice as high got 81% more reviews, from
69% to 94% more. This is not pricing advice. Larger and more polished games can
both charge more and attract more reviews. Niche prices barely vary: half of
games sit in a niche whose median price is exactly $4.99, and 94% in one whose
median is $3.99 to $8.99.

### Free games

The free model uses all 11,989 launches. Every launch was recounted with all
reviews; 4% have no review in the first 30 days.

- Seasonal sales and themed fests have no clear effect.
- A demo out by the last Next Fest went with 95% more reviews, from 9% to 247%
  more, than a later demo. A later demo went with 62% fewer reviews, from 37% to
  77% fewer, than no demo.
- Free competition is counted per single launch, not per 10 as for paid games,
  because a typical free game has only 4 same-niche competitors. Each extra
  same-niche launch went with 5% fewer reviews, from 3% to 6% fewer. With the
  placebo in the same fit, the launch week still has a clear 4% drop per launch,
  from 2% to 6%.
- Thanksgiving through Cyber Monday and Christmas through New Year are
  unconfirmed. Their ranges show 52% fewer reviews, from 35% to 64% fewer, and
  47% fewer, from 25% to 63% fewer, but their chance tests give `p = 0.055` and
  `p = 0.094`, with 4 years each.
- For games with Simplified Chinese, National Day is unconfirmed: its range
  shows 61% fewer reviews, from 40% to 74% fewer, among 36 games, but the pooled
  chance test gives 1.08 with `p = 0.82`. Spring Festival has no clear effect;
  its pooled test gives 1.58 with `p = 0.09`.

### The placebo and weekly competition

The paid model counts the same niche and price-tier competition eight weeks
after launch, when it cannot affect that launch. On the same 65,380 games, ten
more launches in the real week go with 9.4% fewer reviews and the placebo goes
with 8.5% fewer. When both are in one model, the launch week is 5.8% fewer per
ten, from 11.6% fewer to 0.4% more, and no longer clear.

For free games, the placebo is also close to the real result. With both in one
model, the launch week keeps a clear effect, but part of it is still general
crowding.

This is why weekly competition is described, not predicted. A busy cell shows
that a niche and period are crowded. It does not claim that moving to another
week will produce a particular review gain.

### Chinese holidays

Chinese holidays are unconfirmed context only. There are just 5 Spring
Festival and 4 National Day windows. All 9 overlap a Steam sale, Next Fest, or
themed fest, so ordinary intervals overstate certainty. The site shows them
only when Simplified Chinese is selected, without a percentage and never as
general advice.

### Other trust checks

- For paid games, tag niches built from the top 5 or top 20 tags, plain
  competition without price tiers, the same primary tag, and small games only
  all find 7% to 14% fewer reviews per 10 more same-niche launches, against 9%
  in the main fit.
- A two-part check first asks whether a launch got any reviews. A stable
  zero-truncated second part could not be fitted, so it is not used.
- Pre-launch followers would control for hype better. Games Popularity counts
  currently cover 625 launches, including 555 paid and 70 free launches from
  one week in August 2026. Adding followers cuts the paid competition estimate
  by about 80%, and both versions are within noise. This fit stays preliminary
  until 90% of launches since June 2024 have a follower count.
- Fitting on 2022 to 2025 and testing on 16,383 paid launches from 2026 gives a
  rank correlation of 0.485, against 0.384 for a genre, year, and price
  baseline. Same-tier competition fits a little better than plain competition,
  with log-likelihood per game of -3.690 against -3.697, but ranks games a
  little worse, 0.485 against 0.489. The model explains which games get reviews
  better than it explains timing.

## Competition ahead

The heatmap covers the current week and the next 12, a total of 13 weeks. It
filters the announced games by paid or free, language, and tags. Each picked tag
gets a row. A final row combines the tags with the selected all or any rule.

An exact-date game adds 1 to its week. A month or quarter date is divided evenly
across every day still possible, then each week receives the share of those days
that falls inside it. Exact and spread amounts remain visible as separate parts
of a cell. A year-only date uses the same split in a hatched layer that is off by
default. The line below the chart counts all year-only games, including those
beyond the visible weeks.

The default number divides the cell by a typical week. A typical week is the
row's matching full and Early Access launches in the previous 52 weeks divided
by 52. Thus 1.0 means as many launches as that row's average week. Raw-count
mode shows the same cell without the division. When a row averages less than 1
launch a week, the ratios would swing too much, so the row shows unshaded raw
counts.

Weeks more than 4 weeks away are faded and marked as dates still being set.
This is a warning about announcement quality, not a forecast. Selecting a week
lists the exact and spread-date games behind its count. Matching top-10 tags
come first, followed by followers, name, and app ID. Followers are a Games
Popularity count or, failing that, an estimate from the Top Wishlisted rank.

The event lanes show seasonal sales, Next Fest, and themed fests that match a
picked tag. Chinese holidays appear only with Simplified Chinese. A historical
effect appears in an event's label only when the advice rule permits it.

### The held-back niche trend

A trend check compares a niche's share of exact-date upcoming games with its
share of launches in the past 52 weeks. It needs at least 10 exact upcoming
games, 52 past launches, a share ratio of at least 1.45 or at most its inverse,
and a two-proportion test outside the 95% range.

The check flags 4.4% of tags when calibrated on launches against launches, but
about one fifth on today's upcoming list. It is mostly measuring the difference
between announced games and completed launches. The line stays hidden until
daily snapshots can be compared with their later launches, around 2027-01-10.

## Typical for this time of year

This section covers the next 26 weeks. It uses all past games in the selected
paid or free group and languages, not the picked tags. It can look farther than
the heatmap because it uses past seasonal patterns rather than announced dates.

For each past week, the launch count is divided by the average count in its
previous 13 weeks. The estimate for a future week combines:

- the same calendar week in past years;
- the same offset, up to 4 weeks before or after, from recurring Next Fests,
  seasonal sales, and regional holidays.

Each part needs at least 3 past years. Parts with more years and a steadier
history receive more weight. A standard-deviation floor of 0.05 prevents an
almost constant series from taking all the weight. The bar is the weighted
expected value and the box is its spread across years. A value of 1.0 means the
average of the preceding 13 weeks.

Chinese holidays enter this pattern only when Simplified Chinese is selected.
A quiet seasonal week is not necessarily a good launch week.

## Reviews by language

The language sample contains 1,000 paid launches since 2023 with at least 10
reviews from Steam purchases in their first 30 days. Half support Simplified
Chinese and half do not. For each game, Steam was asked for its first-30-day
reviews from Steam purchases in all languages together and in each of 10
languages: English, Simplified Chinese, Traditional Chinese, Russian, Japanese,
Korean, Brazilian Portuguese, German, French, and Spanish from Spain.

The pooled share divides a group's reviews in one language by its reviews in
all languages. The median first finds each game's language share, then takes
the middle game. Other is reviews in languages outside the 10 counted: the
all-language count minus the 10 language counts. The tables come from
`python -m analysis.languages`.

| With Simplified Chinese | Pooled share | Median per game |
|---|---:|---:|
| English | 55.0% | 39.4% |
| Simplified Chinese | 15.8% | 10.7% |
| Traditional Chinese | 1.4% | 0.6% |
| Russian | 8.4% | 2.0% |
| Japanese | 1.8% | 0.8% |
| Korean | 1.7% | 0.4% |
| Portuguese (Brazil) | 2.3% | 0.0% |
| German | 3.5% | 0.0% |
| French | 2.2% | 0.0% |
| Spanish (Spain) | 2.2% | 0.0% |
| Other | 5.8% | 1.7% |

| Without Simplified Chinese | Pooled share | Median per game |
|---|---:|---:|
| English | 69.4% | 78.5% |
| Simplified Chinese | 5.7% | 0.0% |
| Traditional Chinese | 0.7% | 0.0% |
| Russian | 5.9% | 0.0% |
| Japanese | 2.1% | 0.0% |
| Korean | 0.9% | 0.0% |
| Portuguese (Brazil) | 1.9% | 0.0% |
| German | 3.7% | 0.0% |
| French | 2.3% | 0.0% |
| Spanish (Spain) | 2.1% | 0.0% |
| Other | 5.3% | 0.9% |

- This compares games that chose to add Chinese with games that did not, so it
  shows who reviews, not what adding Chinese would gain.
- Pooled shares are pulled by a few big games, so the median is the better guide
  for a small game. Every game here had at least 10 purchase reviews in its first
  30 days, so the smallest games are not in the sample.
- Latin American Spanish and European Portuguese were not counted. Steam's
  review API calls Korean `koreana`.

## Limits

- Reviews are not sales. Their relationship changes with genre, price, region,
  audience, and the kind of game.
- History is today's view of the past. Current price, demo, tags, and Early
  Access state can differ from launch day, and games removed before collection
  began are absent.
- Announced dates slip. Month, quarter, and year dates are divided across their
  possible weeks, but that does not make them firm commitments.
- These are associations, not cause and effect. Large games choose weeks
  differently from small games, and no model can observe every reason.
