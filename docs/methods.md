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
zero and sometimes huge (a third of paid launches get no review in 30 days, a
few get tens of thousands). Each result is a **rate ratio**: 0.90 means 10% fewer
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
- **The game itself:** price and price against its niche's usual price, Early
  Access, demo, franchise, how many games its publisher released before,
  languages, English audio, its 30 most common tags, launch hour.
- **Time:** year, month and day of the week.

## What we found (paid games)

| Launch... | Reviews, compared with otherwise similar launches | Games |
|---|---|---|
| with 10 more launches in its niche and price tier that week | 9% fewer (6% to 11%) | 67,791 (median 15 such launches) |
| during a seasonal sale | 36% fewer (24% to 47%) | 5,310 |
| in the 7 days before a sale | 15% fewer (32% fewer to 7% more) | 5,337 |
| during Next Fest | 18% more (19% fewer to 74% more) | 3,047 |
| with a demo out during the last Next Fest | 69% more (35% to 111%) | 10,394 |
| during a themed fest for one of its tags | 45% fewer (35% to 54%) | 1,008 |
| within 3 days of a big paid release | no clear difference (11% fewer to 17% more) | 21,375 |
| during China's Spring Festival holiday | 37% fewer (13% to 54%) | 1,408 |
| during China's National Day holiday | 57% fewer (35% to 72%) | 1,047 |
| between US Thanksgiving and Cyber Monday | no clear difference (27% fewer to 150% more) | 713 |
| between Christmas and New Year | no clear difference (23% fewer to 76% more) | 741 |
| in Early Access | 16% more (1% fewer to 36% more) | 10,962 |

Reviews x price (the revenue proxy) gives the same picture.

## How much to trust it

- **It is not cause and effect.** Big, hyped games pick their weeks and small
  games avoid them. Every result reads "launches in busier weeks got X% fewer
  reviews on average, after adjusting for ...", never "busy weeks cause X% fewer
  reviews".
- **The competition number fails our placebo test.** The number of same-niche
  launches 8 weeks *after* a game's launch goes with fewer reviews by the same
  amount (1.1% fewer per launch against 1.0% for the real week). With both in
  one model, the real week's effect drops to 0.2% per launch and is no longer
  clear. So the competition number mostly says how crowded a niche and a period
  are in general, not that the chosen week matters. The heatmap's "busy" weeks
  should be read the same way.
- **No hype control yet.** Pre-launch followers would be the best control we
  have, but Games Popularity counts exist so far for 626 launches from one week
  of August 2026. On the 555 paid ones, adding followers shrinks the competition
  effect by about 80% (both versions are within noise). This fit becomes the
  headline once 90% of launches since June 2024 have a follower count.
- **Checks that agree:** niches from the top 5 or top 20 tags instead of 10,
  plain competition without price tiers, the same primary tag, and small games
  only (under $20, no franchise, publisher with at most 2 earlier games) all give
  0.7% to 1.5% fewer reviews per same-niche launch. A hurdle model (one part for
  "any reviews at all", one for "how many, given some") agrees on direction for
  competition, sales and demos: those launches more often got no review at all.
  For themed fests and the Chinese holidays neither part alone is clear, so
  those two results are less sure than their intervals suggest.
- **Free games:** our review counts only include Steam purchases, so most free
  launches show 0 reviews in their first 30 days although they do have reviews.
  The free model is fitted but marked unreliable until free games are counted
  with all purchase types.
- **Today's view of the past:** price, demo, tags and Early Access state are
  today's, not launch day's. Games delisted before we started collecting are
  missing, so older years look a bit better than they were.

## Does it predict?

Fitted on 2022 to 2025 launches and tested on 16,383 paid launches from 2026,
the model ranks games better than a baseline with only genre, year and price
(rank correlation with real reviews 0.49 against 0.39). It explains who gets
more reviews in general far better than it explains anything about timing.
