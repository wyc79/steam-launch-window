# Methods: what history says

This is the text for the website's Methods page (Phase 3). The numbers are from
the 2026-10-12 data. `python -m analysis.model` rebuilds them into
`site/data/model.json`.

## The question

Did games that launched in a busier week, or during a Steam sale or fest, get
fewer reviews in their first 30 days than similar games that launched at other
times?

## The data

- **Launches:** every game released on Steam from 2022-01-01 until 31 days
  before the data date (so the 30-day window has closed): 80,095 launches up to
  2026-09-11. Early Access launches are in, with an Early Access marker. Games
  leaving Early Access (297) are left out: that is not their first launch.
- **Paid and free games are fitted apart.** A game is free if Steam marks it free
  or "Free to Play" is in its top 10 tags. 67,791 paid games, 12,232 free.
- **Outcome:** reviews from Steam buyers written in the first 30 days. Reviews
  stand in for sales, but the ratio varies by genre and price, so we say "more
  reviews", not "more sales". For paid games we also fit reviews x price, a rough
  revenue proxy.

## The model

A negative binomial regression, a standard model for counts that are often
zero and sometimes huge (a quarter of paid launches, 24.7%, get no review in 30
days; a few get tens of thousands). Each result is a **rate ratio**: 0.90 means 10% fewer
reviews on average, 1.20 means 20% more, with everything else in the model held
equal. The 95% interval shows the uncertainty. Launches in the same week share
news cycles and store traffic, so the intervals allow for that (standard errors
clustered by launch week).

What the model adjusts for:

- **Competition:** other launches that week (Monday to Sunday, Pacific time) in
  the same niche, the same price tier and a shared major language. Two games
  are in the same niche when their top 10 tags, weighted by players' tag votes,
  are similar enough (cosine similarity at least 0.3).
- **Steam events** from our events file: seasonal sales and the 7 days before
  them, Next Fest, a demo out during the last Next Fest, themed fests that match
  the game's tags, big releases within 3 days, Chinese and US holidays.
- **The game itself:** its price and its niche's usual price (the median price
  of same-niche launches in the year before it), Early Access, demo, franchise,
  how many games its publisher released before, languages, English audio, the 30
  most common tags, launch hour.
- **Time:** year, month and day of the week.

## What we found (paid games)

The "by chance" column is a second test for events that happened only a few
times (see "How much to trust it"). It estimates the event's effect alone, on
all games pooled with the rest of the model held fixed (the first number, a
rate ratio, so it can differ a little from the main column), then gives how
often fake event dates on random weeks gave a result at least that far from
"no difference" (p). Small p is better; 0.05 means 1 in 20.

| Launch... | Reviews, compared with otherwise similar launches | By chance: effect alone; p | Games |
|---|---|---|---|
| with 10 more launches in its niche and price tier that week | 9% fewer (6% to 11%) | | 67,791 (median 15 such launches) |
| during a seasonal sale | 37% fewer (25% to 47%) | 0.75; 0.001 (19 sales) | 5,310 |
| in the 7 days before a sale | 15% fewer (32% fewer to 6% more) | | 5,337 |
| during Next Fest | 19% more (19% fewer to 75% more) | 1.13; 0.34 (14 fests) | 3,047 |
| with a demo out during the last Next Fest | 71% more (36% to 114%) | | 10,394 |
| during a themed fest for one of its tags | 45% fewer (35% to 54%) | 0.56; 0.04 (69 fests) | 1,008 |
| within 3 days of a big paid release | no clear difference (11% fewer to 18% more) | | 21,375 |
| during China's Spring Festival holiday, without Simplified Chinese | 37% fewer (14% to 54%) | 0.70; 0.08 (5 holidays, all games) | 877 |
| ... with Simplified Chinese | 29% fewer (8% to 46%) | (the same test) | 531 |
| during China's National Day holiday, without Simplified Chinese | 56% fewer (33% to 71%) | 0.51; 0.007 (4 holidays, all games) | 698 |
| ... with Simplified Chinese | 52% fewer (6% to 76%) | (the same test) | 349 |
| between US Thanksgiving and Cyber Monday | no clear difference (25% fewer to 154% more) | 1.26; 0.42 (4) | 713 |
| between Christmas and New Year | no clear difference (23% fewer to 73% more) | 1.11; 0.61 (4) | 741 |
| in Early Access | 18% more (0% to 38% more) | | 10,962 |

Reviews x price (the revenue proxy) gives the same picture.

**Price.** At the same niche price, a game that costs twice as much got 81% more
reviews (69% to 94%). That is not pricing advice: it shows which games charge
more (bigger, more polished ones), not what a price change would do. Niche
prices barely vary (half of all games sit in a niche whose median is $4.99; 90%
between $3.99 and $8.99), so the niche price says little on its own.

**Chinese holidays are not a general rule.** Games launched during China's
holidays got fewer reviews, with or without Simplified Chinese (see the
table). In the review-count model, the extra effect of supporting Simplified
Chinese is 1.13 (0.76 to 1.68) for Spring Festival and 1.09 (0.64 to 1.84) for
National Day: no clear difference, but the intervals are wide, so a difference
is not ruled out. The "any reviews" part does show one: games with Simplified
Chinese launched during Spring Festival were less likely to get any review than
other games launched then (odds ratio 0.71, 0.55 to 0.93). Every one of the 9
holiday windows in the data overlapped another Steam event: the Lunar New Year
Sale (2022), Next Fest (October 2022, February 2024, February 2026), the Autumn
Sale (2025) or a themed fest (the other years). With only 5 and 4 windows, the
usual intervals overstate how sure this is. The chance test, on all games
pooled, agrees for National Day (0.007) but not clearly for Spring Festival
(0.08). The site shows Chinese holidays only as calendar context for games that
support Simplified Chinese, marked unconfirmed, and not as advice for other
games.

## How much to trust it

- **It is not cause and effect.** Big, hyped games pick their weeks and small
  games avoid them. Every result reads "launches in busier weeks got X% fewer
  reviews on average, after adjusting for ...", never "busy weeks cause X% fewer
  reviews".
- **The placebo explains most of the competition number.** We count the same
  thing (same niche, same price tier) 8 weeks *after* each game's launch, when it
  cannot matter. That placebo goes with fewer reviews by as much as the real
  week does (0.9% fewer per launch against 1.0%, on 65,380 games). With both in
  one model, the launch week keeps 0.6% fewer per launch (0% to 1.2%), at the
  edge of noise, and the placebo 0.4%. So most of the competition number is how
  crowded a niche and a period are in general; the chosen week itself adds a
  small effect at most. The heatmap's "busy" weeks should be read the same way.
- **Rare events: a chance test.** Sales, fests and holidays happened only a few
  times (4 to 19 windows; themed fests 69), and the usual intervals assume more
  independent chances than that. So for each one we placed fake windows of the
  same length on random weeks, 1,000 times (same number of windows, the same
  weekday and Pacific clock time, never on a real window of that event, even a
  themed fest for other tags), and counted how often the fake dates gave a
  result at least as far from "no difference" as the real ones. To keep it
  fast, the model is fitted once without the event and only the event's own
  effect is estimated for each set of dates, on all games pooled (for a Chinese
  holiday, with and without Simplified Chinese). On 15 fake sets for two events
  this tracked a full refit closely (correlation above 0.99), and if anything it
  makes the chance numbers a little too large (cautious). Each event has its
  own random numbers, so adding an event does not change the others. Sales
  (0.001), National Day (0.007) and themed fests (0.04) pass; Spring Festival
  (0.08), Next Fest, Thanksgiving and Christmas do not.
- **No hype control yet.** Pre-launch followers would be the best control we
  have, but Games Popularity counts exist so far for 626 launches from one week
  of August 2026. On the 555 paid ones, adding followers shrinks the competition
  effect by about 80% (both versions are within noise). This fit becomes the
  headline once 90% of launches since June 2024 have a follower count.
- **Checks that agree:** niches from the top 5 or top 20 tags instead of 10,
  plain competition without price tiers, the same primary tag, and small games
  only (under $20, no franchise, publisher with at most 2 earlier games, launched
  from 2023 on because our publisher counts start in 2022) all give 0.7% to 1.5%
  fewer reviews per same-niche launch.
- **Zero or some reviews.** A first part, "any reviews at all", shows sales,
  same-tier competition and a demo outside Next Fest going with more launches
  that got no review. Themed fests and the Chinese holidays do not show up there
  for games without Simplified Chinese: their dip is among games that got some
  reviews (a plain count model on those games, not corrected for the missing
  zeros, gives 0.55, 0.59 and 0.45). Games with Simplified Chinese launched
  during Spring Festival are the exception (above). The planned second part, a
  zero-truncated count model, has no stable fit on this data and is left out.
- **Free games:** our review counts only include Steam purchases, so most free
  launches show 0 reviews in their first 30 days although they do have reviews.
  The free model is not fitted, and is marked unreliable, until free games are
  recounted with all reviews. The model checks this in the data: it fits and reads
  the free model once at least 95% of the free launches the sample would include,
  with or without a count, are recounted (`recounted_share` in `model.json`). A
  launch counts as recounted when it has `reviews_purchase=all` and a 30-day
  count. Launches still waiting for their count stay in the total. A recount
  marks every free row `all` when it starts and blanks the counts it will redo,
  so the mark alone would read 100% at once. The free model also stays
  unreliable while more than 80% of its launches have no reviews. If one group's
  fit fails, `model.json` marks it `failed` and still holds the other group.
- **Today's view of the past:** price, demo, tags and Early Access state are
  today's, not launch day's. Games delisted before we started collecting are
  missing, so older years look a bit better than they were.

## Does it predict?

Fitted on 2022 to 2025 launches and tested on 16,383 paid launches from 2026,
the model ranks games better than a baseline with only genre, year and price
(rank correlation with real reviews 0.485 against 0.384). Counting competition
within the same price tier fitted the 2026 launches a little better than plain
competition (log-likelihood per game -3.690 against -3.697), so it is the main
measure, but it ranked them very slightly worse (0.485 against 0.489). The model
explains who gets more reviews in general far better than it explains anything
about timing.
