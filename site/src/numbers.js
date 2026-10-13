// The selection's numbers, computed once and shared: the top bar's count and its
// red and the history panel (What history says) read the same cached objects, as do
// the heatmap and its trend line (Competition ahead) and the outlook (Typical for
// this time of year). Each result holds both groups, so paid / free costs nothing.

import { groupOf, heatmap, historyPanel, matchCount, speaks, trendFrom, weekGames } from "./lib/heatmap.js";
import { outlook } from "./lib/season.js";
import { query } from "./state.js";

const KEEP = 20; // recent selections kept; older ones are computed again
export const OUTLOOK_WEEKS = 26; // the outlook comes from past years, so it can look further than the heatmap

const sorted = (list) => [...list].sort();

// what the outlook depends on: the languages (it is the all-games pattern)
export function outlookKey(st) {
  return JSON.stringify(sorted(st.languages));
}

// what the numbers depend on: tags, mode, languages and the panel's measure (not
// the group, and not the order tags or languages were picked in)
export function numbersKey(st) {
  return JSON.stringify([sorted(st.tags), st.mode, sorted(st.languages), st.measure]);
}

function remember(cache, key, make) {
  if (cache.has(key)) {
    const value = cache.get(key);
    cache.delete(key); // most recent last
    cache.set(key, value);
    return value;
  }
  const value = make();
  cache.set(key, value);
  if (cache.size > KEEP) cache.delete(cache.keys().next().value);
  return value;
}

// Upcoming games per tag id among the games that speak one of `languages` and are
// in `group`, for the tag list.
export function tagCounts(games, { languages, group }) {
  const out = new Map();
  for (const g of games) {
    if (groupOf(g) !== group || !speaks(g.langs, languages)) continue;
    for (const t of g.tags) out.set(t, (out.get(t) ?? 0) + 1);
  }
  return out;
}

// what the heatmap depends on: tags (in the order picked, which is the order of
// its rows), mode and languages; both groups are in each result, and the panel's
// measure does not touch it
export function heatmapKey(st) {
  return JSON.stringify([st.tags, st.mode, sorted(st.languages)]);
}

// today: the snapshot date, the heatmap's first week
export function createNumbers(games, history, today) {
  const results = new Map();
  const perTag = new Map();
  const maps = new Map();
  const perRow = new Map();
  const trends = new Map();
  const outlooks = new Map();
  let outlookEvents = null;
  let byId = null;
  // one heatmap row, kept on its own: picking a second tag reuses the first tag's row
  const row = (tags, st) =>
    remember(perRow, JSON.stringify([sorted(tags), tags.length > 1 ? st.mode : "", sorted(st.languages)]), () => ({
      tags,
      ...heatmap(games, today, { selection: tags, mode: st.mode, languages: st.languages, history }),
    }));
  const numbers = {
    has: (st) => results.has(numbersKey(st)),
    hasHeatmap: (st) => maps.has(heatmapKey(st)),
    // what heatmapRows(...) gives with the typical week, for the heatmap (each
    // tag alone, then the combination; test/numbers.test.js checks they agree)
    heatmap: (st) =>
      remember(maps, heatmapKey(st), () => {
        const rows = st.tags.map((t) => row([t], st));
        if (st.tags.length !== 1) rows.push(row([...st.tags], st));
        return rows;
      }),
    // the niche trend for each heatmap row, in the same order (null for the all-games
    // row): trendFrom(row, all games' row), what nicheTrend(...) gives
    trend: (st) =>
      remember(trends, heatmapKey(st), () => {
        const everyone = row([], st);
        return numbers.heatmap(st).map((r) => (r.tags.length ? trendFrom(r, everyone) : null));
      }),
    // the seasonal outlook (both groups) for the selection's languages, from the
    // pattern of all games; events: events.json's list ([] when it failed)
    hasOutlook: (st, events) => outlookEvents === events && outlooks.has(outlookKey(st)),
    outlook: (st, events) => {
      if (outlookEvents !== events) {
        outlooks.clear();
        outlookEvents = events;
      }
      return remember(outlooks, outlookKey(st), () =>
        outlook(history, events, today, { weeks: OUTLOOK_WEEKS, languages: st.languages }),
      );
    },
    // one row's games in one week, for the picked group, in weekGames' order; on
    // demand, not cached (one pass over the upcoming games)
    weekGames: (st, tags, week, year) =>
      weekGames(games, today, week, { selection: tags, mode: st.mode, languages: st.languages, year }).filter(
        (g) => groupOf(g) === st.group,
      ),
    // appid -> upcoming game
    game: (appid) => {
      byId ??= new Map(games.map((g) => [g.appid, g]));
      return byId.get(appid);
    },
    // { counts: matchCount(...), panel: historyPanel(...) } for the selection
    get: (st) =>
      remember(results, numbersKey(st), () => {
        const q = query(st);
        return { counts: matchCount(games, history, q), panel: historyPanel(history, { ...q, measure: st.measure }) };
      }),
    // tag id -> upcoming games, for the selection's languages and group (tags do not change it)
    tagCounts: (st) =>
      remember(perTag, JSON.stringify([sorted(st.languages), st.group]), () => tagCounts(games, st)),
  };
  return numbers;
}
