// Trends: the selection's past launches per quarter, from 2022 Q1 to the quarter
// of `today` (partial: launches before `today`). A port of analysis/trends.py,
// which is the reference and documents the rules; test/golden.test.js checks this
// file against it.

import { makeDay, parts, toDay, toIso } from "./dates.js";
import { GROUPS, PANEL_TYPES, groupOf, matches, speaks } from "./heatmap.js";

export const TREND_FROM = "2022-01-01"; // the history data starts here, on a quarter's first day
export const RECENT_FULL = 2; // full quarters before the partial one that are marked recent (trends.py)

const quarterOf = (month) => Math.floor((month - 1) / 3) + 1;

// 2022 Q1 to the quarter that holds `today`: label parts, first and last day, its
// length, how many of its days are counted, whether it is the partial one, and
// whether it is recent (the partial one and the RECENT_FULL before it: may still change)
export function quarters(today) {
  const now = toDay(today);
  const { year: thisYear, month } = parts(now);
  const current = makeDay(thisYear, 3 * (quarterOf(month) - 1) + 1, 1);
  const out = [];
  let { year } = parts(toDay(TREND_FROM));
  let q = 1;
  for (let start = toDay(TREND_FROM); start <= current; ) {
    const next = q === 4 ? makeDay(year + 1, 1, 1) : makeDay(year, 3 * q + 1, 1);
    const partial = start === current;
    out.push({
      year,
      q,
      start: toIso(start),
      end: toIso(next - 1),
      length: next - start,
      days: partial ? now - start : next - start,
      partial,
    });
    start = next;
    [year, q] = q === 4 ? [year + 1, 1] : [year, q + 1];
  }
  out.forEach((x, i) => (x.recent = i >= out.length - 1 - RECENT_FULL));
  return out;
}

// Past launches per quarter for the selection (niche) and all games of the same
// group and languages (all), with share and running totals. See trends.py quarterly.
export function quarterly(history, today, { selection = [], mode = "and", languages = [] } = {}) {
  const qs = quarters(today);
  const index = new Map(qs.map((q, i) => [`${q.year} ${q.q}`, i]));
  const niche = Object.fromEntries(GROUPS.map((g) => [g, qs.map(() => 0)]));
  const every = Object.fromEntries(GROUPS.map((g) => [g, qs.map(() => 0)]));
  for (const h of history) {
    const day = h.launch_date;
    if (!PANEL_TYPES.includes(h.launch_type) || !(TREND_FROM <= day && day < today) || !speaks(h.langs, languages)) {
      continue;
    }
    const i = index.get(`${+day.slice(0, 4)} ${quarterOf(+day.slice(5, 7))}`);
    const group = groupOf(h);
    every[group][i] += 1;
    if (matches(h.tags, selection, mode)) niche[group][i] += 1;
  }
  const out = { quarters: qs };
  for (const g of GROUPS) {
    let run = 0;
    let runAll = 0;
    out[g] = niche[g].map((n, i) => {
      const a = every[g][i];
      run += n;
      runAll += a;
      return { niche: n, all: a, share: a ? n / a : null, cumulative: run, cumulative_all: runAll };
    });
  }
  return out;
}
