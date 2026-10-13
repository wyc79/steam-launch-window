// The selection's numbers, computed once and shared: the top bar's count and its
// red, and (step 4) section 03's history panel read the same cached objects.
// matchCount and historyPanel give both groups, so paid / free costs nothing.

import { groupOf, historyPanel, matchCount, speaks } from "./lib/heatmap.js";
import { query } from "./state.js";

const KEEP = 20; // recent selections kept; older ones are computed again

const sorted = (list) => [...list].sort();

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

export function createNumbers(games, history) {
  const results = new Map();
  const perTag = new Map();
  return {
    has: (st) => results.has(numbersKey(st)),
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
}
