# Steam endpoints

What we checked, how each endpoint behaves, and what we will use it for.
All checks were run on 2026-10-10 from a home connection, with
User-Agent `steam-launch-window/0.1 (+https://github.com/wyc79/steam-launch-window)`
and about 1.5 s between requests.

Steam changes these endpoints without notice. Re-check before relying on
anything here, and update this file when behavior changes.

## Summary

| Need | Source | Key? | Status |
|---|---|---|---|
| Full app list | `IStoreService/GetAppList` | yes | works |
| Upcoming games by tag | `IStoreQueryService/Query`, store search | no | works |
| Wishlist rank | store search `filter=popularwishlist` | no | works, top ~5,300 only |
| App details | `IStoreBrowseService/GetItems` (bulk), `appdetails` (single) | no | works |
| User tags | `GetItems` (with weights), SteamSpy (vote counts, released only) | no | works |
| Followers | community `memberslistxml` `memberCount` | no | works, 1 request per app, strict rate limit |
| First-30-day reviews | `appreviews` with a date range | no | works, checked exactly |
| Tag names | `IStoreService/GetTagList` | no | works |
| PICS / appinfo | `steam` Python lib, anonymous login | no | works locally, not tested in Actions |

Rate limits: we sent about 250 requests to `store.steampowered.com`,
`api.steampowered.com` and `steamcommunity.com` over the session and got
no 429s or errors. We did not stress test. Community reports say
`appdetails` allows about 200 requests per 5 minutes; we have not confirmed this.
Plan for 1 request per second per host, with backoff on 429 and 5xx.

## 1. Full app list

`ISteamApps/GetAppList/v2` is **gone** (404, "Method not found").

Use `GET https://api.steampowered.com/IStoreService/GetAppList/v1/`

- Params: `key` (required, else 403), `include_games`, `include_dlc`,
  `include_software`, `include_videos`, `include_hardware` (`true`/`false`),
  `max_results` (up to 50000), `last_appid` (paging), `if_modified_since` (unix time).
- Response: `{"response": {"apps": [{"appid", "name", "last_modified", "price_change_number"}], "have_more_results", "last_appid"}}`
- Games only: 192,145 apps in 4 pages, about 20 MB, 13 s.
- Includes unreleased and TBA games.
- `if_modified_since` returns only apps changed since then. Good for daily deltas.
- The key lives in `.env` locally and will be a GitHub Actions secret.
  It is a Web API key, not a login, so this is allowed under our rules.

We probably do not need this list. `Query` (below) lists upcoming and
released games directly. Keep it as a fallback and for spot checks.

## 2. Upcoming games by tag

### 2a. `IStoreQueryService/Query` (main source)

`GET https://api.steampowered.com/IStoreQueryService/Query/v1/?input_json=...`

No key needed. Field names come from the protobufs at
github.com/SteamDatabase/Protobufs (`webui/service_storequery.proto`).

```json
{
  "query": {
    "start": 0, "count": 1000, "sort": 2,
    "filters": {
      "coming_soon_only": true,
      "type_filters": {"include_games": true},
      "tagids_must_match": [{"tagids": [492]}, {"tagids": [1664]}]
    }
  },
  "context": {"language": "english", "country_code": "US", "steam_realm": 1},
  "data_request": {"include_release": true, "include_tag_count": 20, "include_basic_info": true}
}
```

- Response: `{"response": {"metadata": {"total_matching_records", "start", "count"}, "ids": [...], "store_items": [...]}}`.
  `store_items` has the same shape as `GetItems` (section 4).
- `count` max is 1000.
- **Paging quirk:** with the default sort (0) or sort 3, pages overlap and
  some items are never returned (1,216 unique of 1,364). With `sort: 1` or
  `sort: 2`, paging returned every item. Use `sort: 2` and check that
  the unique count equals `total_matching_records`.
- Tag filter: each object in `tagids_must_match` is ANDed; tag IDs inside
  one object are ORed. Checked: Indie = 23,475; Indie AND Puzzle = 3,886;
  Indie OR Puzzle = 28,597.
- `coming_soon_only` returns 60,009 games. Most have no usable date:
  `text_comingsoon` 27,515, `text_tba` 15,293, missing 264.
  Dated ones: `date_full` 4,335, `date_month` 2,376, `date_quarter` 4,368,
  `date_year` 5,858 (16,937 total).
- Full pass (60 calls, include tags and release): 128 s.
- Other sort values (10 to 13, 20, 30) put big games first, but their exact
  meaning is undocumented. Do not use them as a hype metric.
- `release_date_filter: {"release_date_type": 1, "start_date", "end_date"}`
  plus `released_only: true` lists games released in a date range
  (Feb 2024: 1,364 games, Balatro included). Use this for history.
  `release_date_type` 0 ignores the range; 2 returned only 2 games (meaning unknown).

### 2b. Store search, JSON mode (backup and wishlist rank)

`GET https://store.steampowered.com/search/results/`

- Params: `query=`, `start`, `count`, `filter`, `tags` (comma list = AND),
  `category1=998` (games only), `sort_by`, `infinite=1` (JSON mode), `cc=us`, `l=english`.
- Response: `{"success": 1, "results_html": "<a ...>...", "total_count", "start"}`.
  The rows are HTML. Each row has `data-ds-appid`, `data-ds-tagids`
  (top ~7 tags only), a `title` span, and a `search_released` div with the
  display date string.
- `count`: max 100. Smaller values still returned 25 rows.
- Deep paging works to the end (`start=9800` worked; past the end returns empty).
- `filter=comingsoon`: 17,582 items (all types), sorted by date with
  precise dates first (day, then month, quarter, year). Mostly leaves out
  "Coming soon" and "To be announced". Includes demos unless `category1=998`.
- `filter=popularcomingsoon`: 62,717 items. Roughly date order with a small
  popularity boost. It is **not** a clean popularity rank.
- `sort_by=Released_DESC&category1=998`: all released games (123,660), newest first.
- Rate limit: from a home IP, 1 request per second ran without errors. From a
  GitHub Actions runner (2026-10-11), the wishlist crawl at 1 per second got
  429 four times around page 30, then recovered after backoff. The daily job
  now spaces store search requests 2 seconds apart.

## 3. Wishlist rank (main pre-launch hype proxy)

`filter=popularwishlist` on store search (section 2b).

- 5,343 unreleased games in the list (2,074 with the Indie tag). Games below
  that cutoff have no rank.
- Order was identical across repeated calls.
- A tag-filtered list keeps the same relative order as the global list,
  so one global crawl (54 pages of 100) gives a global rank for every listed game.
- It is a rank, not a wishlist count. Steam does not publish wishlist counts.
- Includes TBA and "Coming soon" games, which is fine for rank but they
  will not appear on the weekly heatmap.

## 4. App details

### 4a. `IStoreBrowseService/GetItems` (bulk, preferred)

`GET https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json=...`

No key needed.

```json
{
  "ids": [{"appid": 3115160}, {"appid": 2719590}],
  "context": {"language": "english", "country_code": "US", "steam_realm": 1},
  "data_request": {"include_release": true, "include_tag_count": 20,
                   "include_basic_info": true, "include_reviews": true}
}
```

- Batch: 250 IDs worked (URL about 7.8 KB). 300 failed with 414 (URL too long).
  Use 200. Invalid or hidden apps come back with `success` other than 1.
- `release`:
  - `steam_release_date`: unix time.
  - `coming_soon_display`: `date_full`, `date_month`, `date_quarter`,
    `date_year`, `text_tba`, `text_comingsoon`. This is the date precision.
  - For month, quarter and year, the timestamp is the **last day** of the
    period at 00:00 Pacific (for example "November 2026" = 2026-11-30 08:00 UTC).
  - For full dates the timestamp includes the release hour. Convert to
    America/Los_Angeles before taking the calendar date.
  - `custom_release_date_message` holds text like "To be announced".
  - `is_early_access`: true for upcoming Early Access launches.
  - `original_steam_release_date`: present for some games that left Early
    Access (Hades: EA start Dec 2019). Missing for others (Baldur's Gate 3).
- `tagids` and `tags: [{"tagid", "weight"}]`, ordered by weight. Works for unreleased games.
- `basic_info`: `developers`, `publishers`, `franchises`.
- `related_items.demo_appid`: the current demo app ID.
- `reviews.summary_filtered`: `review_count`, `percent_positive`, `review_score`.
- `categories`, `best_purchase_option` (current price) also available.

### 4b. `appdetails` (one app per call)

`GET https://store.steampowered.com/api/appdetails?appids=<id>&cc=us&l=english`

- Response: `{"<id>": {"success": true, "data": {...}}}`.
- Fields we checked: `release_date: {"coming_soon", "date"}` (the display
  string, for example "Oct 14, 2026" or "To be announced"), `price_overview`
  (`initial`, `final`, `discount_percent`, in cents), `is_free`,
  `genres` (Early Access is genre id 70), `categories`, `developers`,
  `publishers`, `demos: [{"appid"}]`.
- Several IDs in one call return 400, unless you add `filters=price_overview`.
- Use only when GetItems lacks something. It is slow at scale.

## 5. User tags

- `GetItems` gives tag IDs with weights (section 4a). This is enough for us.
- Store page (`/app/<id>/`) has `InitAppTagModal(...)` JSON with
  `{"tagid", "name", "count"}` (vote counts). Needs HTML scraping; not needed.
- SteamSpy `https://steamspy.com/api.php?request=appdetails&appid=<id>`:
  `tags` as `{"name": votes}` for released games. For unreleased games it
  returns empty tags and zeros. SteamSpy's own docs ask for at most 1 request per second.

## 6. Followers

`GET https://steamcommunity.com/games/<appid>/memberslistxml/?xml=1&p=99999`

- `memberCount` is the size of the game's community hub group, which is what
  "following" a game joins. This is the number usually called followers.
- Default page (`p=1`) is about 42 KB and lists 1,000 member Steam IDs.
  We do not want personal data. A page past the end (`p=99999`) still
  returns `memberCount` in about 1 KB with no IDs. Always use that, and
  store only the count.
- Works for unreleased games (Light No Fire: 248,708; a small new game: 2).
- `Cache-Control: max-age=300`.
- Cost: one request per app.
- **Rate limit (found 2026-10-10):** after about 10 requests spread over the
  Phase 0 checks, the first request of a 1/s run got 429, and so did every
  request after it, including the plain hub page (`/app/<id>`). The block
  was still on 31 minutes later. A cached copy can still return 200, which
  hides the block. Requests made while blocked seem to extend it, so stop
  completely on 429 and wait. The safe rate is still being measured.
- Because of this, followers are only tracked for about 11,000 games
  (see the README), not all 60,000.
- Not yet spot-checked against SteamDB. Do this by hand for a few games.

## 7. Reviews

### 7a. `appreviews`

`GET https://store.steampowered.com/appreviews/<appid>?json=1`

- Params: `filter=recent` (newest first; needed for date ranges and cursor paging),
  `language=all`, `purchase_type=all`, `num_per_page` (max 100),
  `cursor` (start with `*`, then the returned `cursor`),
  `filter_offtopic_activity=0` (include review-bomb periods).
- Response: `{"success", "query_summary": {"num_reviews", "review_score", "total_positive", "total_negative", "total_reviews"}, "reviews": [...], "cursor"}`.
- Each review has `timestamp_created`, `voted_up`, `written_during_early_access`,
  `steam_purchase`, `received_for_free`, `author`, and more.
- **Date-range count in one call:** add `start_date=<unix>&end_date=<unix>&date_range_type=include&num_per_page=0`.
  `query_summary.total_reviews` is then the count in that window.
  Checked against a full cursor walk on 3 games released in Aug 2026:
  746 = 746, 142 = 142, 158 = 158. On a game released 2 days earlier it said
  101 vs 96 by cursor walk, probably cache lag.
- `day_range` did not change the summary totals.
- Caveat: counts are reviews written in the window that **still exist today**.
  Deleted reviews are gone.
- `purchase_type=steam` with the default off-topic filter matches the store's
  own review count (checked on 3 games: 101 = 101, 33 = 33, 1,584 vs 1,568).
  `purchase_type=all` adds key activations (curator and giveaway copies),
  about 5 to 10% more. The pipeline uses `steam`, so the 30-day count can be
  compared with the summary count, and a summary count of 0 means 0.

### 7b. Review histogram

`GET https://store.steampowered.com/appreviewhistogram/<appid>?l=english&review_score_preference=0`

- Response: `{"success", "results": {"start_date", "end_date", "rollup_type", "rollups": [{"date", "recommendations_up", "recommendations_down"}], "recent": [...]}}`.
- `rollup_type` is `week` for young games and `month` for older ones,
  so it cannot give an exact 30-day count for older games. Use 7a instead.

## 8. Tag ID to name

- `GET https://api.steampowered.com/IStoreService/GetTagList/v1/?language=english`
  No key. 446 tags. Has `version_hash` to detect changes. **Use this.**
- `IStoreService/GetMostPopularTags/v1` and
  `store.steampowered.com/tagdata/populartags/english` (429 tags) are subsets.

## 9. PICS / appinfo

Tested with the `steam` Python package (1.4.4, with gevent) and `anonymous_login()`.

- Anonymous login works. No personal account. It took 22 s.
- `get_product_info(apps=[...])`: 1,000 IDs in one call, 24 s.
- `common` has `type`, `releasestate` (`released` / `prerelease`),
  `store_tags` (top 20 IDs in order, no weights), `genres`, `category`,
  `associations` (developer, publisher, franchise), `review_score`, `review_percentage`.
- **For unreleased games, anonymous access hides the release date**
  (`public_only: 1`, `_missing_token`). `steam_release_date` is only set for released games.
- `get_changes_since(1)` returned no app changes, so PICS is not a way to get the full app list.
- Not tested in GitHub Actions. Testing it needs a pushed workflow.
- Verdict: it adds nothing that `GetItems` lacks, and it is a heavier dependency.
  **Do not use it for now.**

## Recommendation

| Field | Source |
|---|---|
| Upcoming game list | `Query` with `coming_soon_only`, `sort: 2`, pages of 1000 |
| Tags (IDs, weights) | `Query` / `GetItems` |
| Release date, precision | `GetItems` `release` (timestamp + `coming_soon_display`), keep the display string as `raw` |
| Early Access (upcoming) | `GetItems` `release.is_early_access` |
| Price | `GetItems` `best_purchase_option` (current price) |
| Developer, publisher | `GetItems` `basic_info` |
| Demo | `GetItems` `related_items.demo_appid` |
| Wishlist rank | store search `filter=popularwishlist`, full crawl daily |
| Followers | `memberslistxml?p=99999`, only `memberCount` |
| Historical launches | `Query` with `released_only` + `release_date_filter`, month by month |
| First-30-day reviews | `appreviews` date-range count |
| Early Access at launch (history) | `release.original_steam_release_date` when present, else check `written_during_early_access` on launch-window reviews |
| Tag names | `GetTagList` |
| Full app list | `GetAppList` (keyed), fallback only |

### What hype proxy is really available

1. **Wishlist rank** for the top ~5,300 unreleased games. Ordinal, daily, cheap
   (54 requests). Most small indie games are not in it.
2. **Follower count** for every game. A real number, but one request per app.
   Plan: daily for games dated inside the next 26 weeks, weekly for the rest.
3. Nothing else is usable. Wishlist counts are not public.
   `popularcomingsoon` and the `Query` sort orders are not clean ranks.

### Known limits for the history data

- Demo, price and Early Access fields show **today's** state, not the state
  at launch. A demo removed after launch will not show up. Price is today's price.
- Review counts are only reviews that still exist.
- Games that were delisted do not appear in `Query`, so history is biased
  toward games that are still on sale.
