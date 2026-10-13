// The site's numbers for the heatmap, the match count and the history panel.
// A port of analysis/heatmap.py, which is the reference and documents the rules;
// test/golden.test.js checks this file against it. Games are objects with the
// columns of upcoming.json and history.json, tags as ids (data.js fromTable).

import { toDay, toIso, parts, weekStartDay } from "./dates.js";

export const WEEKS = 13; // Competition ahead: a quarter (heatmap.py WEEKS)
const SPREAD = ["month", "quarter"];
export const GROUPS = ["paid", "free"];
const CELL = ["exact", "spread", "year", "hype", "year_hype", "no_hype"];
const PARTS = ["quiet", "normal", "busy"];
export const PANEL_TYPES = ["full", "early_access"];
export const MIN_GROUP = 30;
export const RELATIVE_WEEKS = 13; // the relative busy measure compares a week with this many weeks before it
export const TYPICAL_WEEKS = 52; // the heatmap's normalized view compares with launches over this many weeks
export const LATER_AFTER = 2; // year-only dates more than this many years ahead ("2099") are summed as "later"
export const TREND_MIN_EXACT = 10; // the niche trend needs this many niche games with exact dates
export const TREND_RATIO = 1.45; // and a share at least this many times the past one, or at most its inverse (trend_calibration.py)
export const TREND_Z = 1.959964; // and a pooled two-proportion z at least this large
export const MODES = ["and", "or"];
export const MEASURES = ["relative", "raw"];

export function groupOf(game) {
  return game.free ? "free" : "paid";
}

export function matches(tags, selection, mode = "and") {
  if (!MODES.includes(mode)) throw new Error(`mode must be one of ${MODES}, not ${mode}`);
  if (!selection.length) return true;
  return mode === "and" ? selection.every((t) => tags.includes(t)) : selection.some((t) => tags.includes(t));
}

// true if the game supports at least one of the user's languages (none chosen: all games)
export function speaks(langs, languages) {
  return !languages.length || langs.some((x) => languages.includes(x));
}

export function selected(games, { selection = [], mode = "and", languages = [] } = {}) {
  return games.filter((g) => matches(g.tags, selection, mode) && speaks(g.langs, languages));
}

function perGroup(games) {
  const out = Object.fromEntries(GROUPS.map((g) => [g, 0]));
  for (const game of games) out[groupOf(game)] += 1;
  return out;
}

// The top bar's numbers per group, so they agree with the heatmap for the picked
// group: [matched, total] for upcoming games and past launches (full and Early
// Access, as in the panel).
export function matchCount(games, history, { selection = [], mode = "and", languages = [] } = {}) {
  const past = history.filter((h) => PANEL_TYPES.includes(h.launch_type));
  const up = perGroup(selected(games, { selection, mode, languages }));
  const upAll = perGroup(games);
  const hist = perGroup(selected(past, { selection, mode, languages }));
  const histAll = perGroup(past);
  return Object.fromEntries(
    GROUPS.map((g) => [g, { upcoming: [up[g], upAll[g]], past: [hist[g], histAll[g]] }]),
  );
}

// the part of a vague date's range from `today` on (days), or null if it has run out
function daysAhead(game, today) {
  const start = Math.max(toDay(game.date), today);
  const end = toDay(game.date_end);
  return start <= end ? [start, end] : null;
}

function overlap(start, end, week) {
  return Math.max(0, Math.min(end, week + 6) - Math.max(start, week) + 1);
}

function emptyCell() {
  return Object.fromEntries(CELL.map((k) => [k, 0]));
}

// Per week and group: exact, spread, year, hype, year_hype, no_hype; `sometime`
// per year; `typical` (with `history`) per group; `matched` and `total` per group.
export function heatmap(games, today, { selection = [], mode = "and", languages = [], history = null } = {}) {
  const now = toDay(today);
  const first = weekStartDay(now);
  const weeks = Array.from({ length: WEEKS }, (_, i) => first + 7 * i);
  const grid = Object.fromEntries(GROUPS.map((g) => [g, weeks.map(emptyCell)]));
  const sometime = {};
  const chosen = selected(games, { selection, mode, languages });
  const lastYear = parts(now).year + LATER_AFTER;
  for (const game of chosen) {
    const group = groupOf(game);
    const followers = game.followers ?? null;
    const precision = game.precision;
    if (precision === "day") {
      const i = (weekStartDay(toDay(game.date)) - first) / 7;
      if (i >= 0 && i < WEEKS) {
        const cell = grid[group][i];
        cell.exact += 1;
        cell.hype += followers ?? 0;
        cell.no_hype += followers === null ? 1 : 0;
      }
      continue;
    }
    if (!SPREAD.includes(precision) && precision !== "year") continue; // no date (ranked only): not on the heatmap
    const span = daysAhead(game, now);
    if (span === null) continue;
    const perDay = 1 / (span[1] - span[0] + 1);
    const isYear = precision === "year";
    const [layer, hype] = isYear ? ["year", "year_hype"] : ["spread", "hype"];
    weeks.forEach((week, i) => {
      const share = perDay * overlap(span[0], span[1], week);
      if (share) {
        const cell = grid[group][i];
        cell[layer] += share;
        cell[hype] += share * (followers ?? 0);
        if (!isYear) cell.no_hype += share * (followers === null ? 1 : 0);
      }
    });
    if (isYear) {
      const key = +game.date.slice(0, 4) <= lastYear ? game.date.slice(0, 4) : "later";
      sometime[key] ??= Object.fromEntries(GROUPS.map((g) => [g, { games: 0, hype: 0, no_hype: 0 }]));
      const year = sometime[key][group];
      year.games += 1;
      year.hype += followers ?? 0;
      year.no_hype += followers === null ? 1 : 0;
    }
  }
  let typical = null;
  if (history != null) {
    const since = toIso(now - 7 * TYPICAL_WEEKS);
    const until = toIso(now);
    const recent = selected(history, { selection, mode, languages }).filter(
      (h) => PANEL_TYPES.includes(h.launch_type) && since <= h.launch_date && h.launch_date < until,
    );
    typical = Object.fromEntries(
      GROUPS.map((g) => [g, recent.filter((h) => !!h.free === (g === "free")).length / TYPICAL_WEEKS]),
    );
  }
  const years = Object.keys(sometime).sort();
  return {
    weeks: weeks.map(toIso),
    ...grid,
    typical,
    sometime: Object.fromEntries(years.map((y) => [y, sometime[y]])),
    matched: perGroup(chosen),
    total: perGroup(games),
  };
}

// The heatmap's rows: each picked tag alone, then the combination in `mode`
// (no tags: one row of all games; one tag: just its row).
export function heatmapRows(games, today, { selection = [], mode = "and", languages = [], history = null } = {}) {
  const out = selection.map((t) => ({
    tags: [t],
    ...heatmap(games, today, { selection: [t], mode, languages, history }),
  }));
  if (selection.length !== 1) {
    out.push({ tags: [...selection], ...heatmap(games, today, { selection, mode, languages, history }) });
  }
  return out;
}

const sum = (cells, f) => cells.reduce((a, c) => a + f(c), 0);

// The niche trend from four counts: niche and all games with exact dates in the
// upcoming weeks, niche and all launches in the past year. See heatmap.py trend_test.
export function trendTest(exact, exactAll, past, pastAll) {
  const shareUp = exactAll ? exact / exactAll : null;
  const sharePast = pastAll ? past / pastAll : null;
  const ratio = shareUp !== null && sharePast ? shareUp / sharePast : null;
  let z = null;
  if (exactAll && pastAll) {
    const pooled = (exact + past) / (exactAll + pastAll);
    const se = Math.sqrt(pooled * (1 - pooled) * (1 / exactAll + 1 / pastAll));
    z = se ? (shareUp - sharePast) / se : 0;
  }
  const clear =
    ratio !== null &&
    z !== null &&
    exact >= TREND_MIN_EXACT &&
    past >= TYPICAL_WEEKS &&
    (ratio >= TREND_RATIO || ratio <= 1 / TREND_RATIO) &&
    Math.abs(z) >= TREND_Z;
  return { ratio, exact, exact_all: exactAll, past, past_all: pastAll, z, clear };
}

// The niche trend from two heatmaps (with `history`) for the same languages and
// today: the niche's and all games'. See nicheTrend.
export function trendFrom(niche, everyone) {
  return Object.fromEntries(
    GROUPS.map((g) => [
      g,
      trendTest(
        sum(niche[g], (c) => c.exact),
        sum(everyone[g], (c) => c.exact),
        Math.round(niche.typical[g] * TYPICAL_WEEKS),
        Math.round(everyone.typical[g] * TYPICAL_WEEKS),
      ),
    ]),
  );
}

// Per group, the niche's share of upcoming games (exact dates in the heatmap's
// weeks) over its share of the launches in the last TYPICAL_WEEKS, with
// `clear` when the site should say so. No tags: null. See heatmap.py niche_trend.
export function nicheTrend(games, history, today, { selection = [], mode = "and", languages = [] } = {}) {
  if (!selection.length) return null;
  return trendFrom(
    heatmap(games, today, { selection, mode, languages, history }),
    heatmap(games, today, { languages, history }),
  );
}

// The default view, "1.0 = a usual week": exact, spread and year over the group's
// typical week. Null without `typical`; a group whose typical week is 0 gets null.
export function normalized(h) {
  if (h.typical === null) return null;
  return Object.fromEntries(
    GROUPS.map((g) => {
      const t = h.typical[g];
      return [g, t ? h[g].map((c) => ({ exact: c.exact / t, spread: c.spread / t, year: c.year / t })) : null];
    }),
  );
}

// by code point, as Python compares strings (< compares UTF-16 units, which puts
// characters above U+FFFF, like emoji, before U+E000 to U+FFFF)
function compareText(a, b) {
  const x = [...a];
  const y = [...b];
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i].codePointAt(0) - y[i].codePointAt(0);
    if (d) return d;
  }
  return x.length - y.length;
}

// The games behind one heatmap week (`week` is its Monday), as the heatmap counts
// them, top-10 tag matches first, then the most followers, then by name, then appid.
// `hype_src` says where `followers` comes from ("f" a count, "r" an estimate from
// wishlist rank); `moved` is [kind, old date text, days since the change].
export function weekGames(games, today, week, { selection = [], mode = "and", languages = [], year = false } = {}) {
  const now = toDay(today);
  const monday = toDay(week);
  const out = [];
  for (const game of selected(games, { selection, mode, languages })) {
    const precision = game.precision;
    let layer, share;
    if (precision === "day") {
      if (weekStartDay(toDay(game.date)) !== monday) continue;
      [layer, share] = ["exact", 1];
    } else if (SPREAD.includes(precision) || (year && precision === "year")) {
      const span = daysAhead(game, now);
      const days = span ? overlap(span[0], span[1], monday) : 0;
      if (!days) continue;
      layer = precision === "year" ? "year" : "spread";
      share = (1 / (span[1] - span[0] + 1)) * days; // as in heatmap, to the last digit
    } else {
      continue;
    }
    const moved = game.moved ?? null;
    out.push({
      appid: game.appid,
      name: game.name,
      free: game.free,
      layer,
      share,
      followers: game.followers ?? null,
      hype_src: game.hype_src ?? null,
      top10: matches(game.tags.slice(0, 10), selection, mode),
      moved: moved ? [moved[0], moved[1], now - toDay(moved[2])] : null,
    });
  }
  return out.sort(
    (a, b) =>
      b.top10 - a.top10 ||
      (a.followers === null) - (b.followers === null) ||
      (b.followers ?? 0) - (a.followers ?? 0) ||
      compareText(a.name, b.name) ||
      a.appid - b.appid,
  );
}

// linear interpolation between the closest ranks (numpy's default), q in 0..1
export function percentile(values, q) {
  if (!values.length) throw new Error("percentile of no values");
  const v = [...values].sort((a, b) => a - b);
  const pos = (v.length - 1) * q;
  const lo = Math.trunc(pos);
  const hi = Math.min(lo + 1, v.length - 1);
  return v[lo] + (v[hi] - v[lo]) * (pos - lo);
}

// Python's round(x, 2): the nearest number with 2 decimals, exact halves to the
// even one. toFixed also rounds the exact binary value but sends halves away from
// zero; a double is an exact half only when it is an odd number of eighths (0.125).
export function round2(x) {
  const eighths = x * 8;
  if (Number.isInteger(eighths) && eighths % 2 !== 0) {
    const down = Math.floor(x * 100); // x * 100 is exact here
    return (down % 2 === 0 ? down : down + 1) / 100;
  }
  return Number(x.toFixed(2));
}

// Past launches in the selection, per group, split into quiet, normal and busy
// launch weeks by tercile of "busy" (see history_panel in heatmap.py).
export function historyPanel(
  history,
  { selection = [], mode = "and", languages = [], minGroup = MIN_GROUP, measure = "relative" } = {},
) {
  if (!MEASURES.includes(measure)) throw new Error(`measure must be one of ${MEASURES}, not ${measure}`);
  const chosen = selected(history, { selection, mode, languages }).filter((h) => PANEL_TYPES.includes(h.launch_type));
  const weekOf = new Map(chosen.map((h) => [h, weekStartDay(toDay(h.launch_date))]));
  const perWeek = new Map();
  for (const h of chosen) {
    const key = `${groupOf(h)} ${weekOf.get(h)}`;
    perWeek.set(key, (perWeek.get(key) ?? 0) + 1);
  }
  const count = (group, week) => perWeek.get(`${group} ${week}`) ?? 0;
  let baselineFrom = null;
  for (const h of history) {
    const week = weekStartDay(toDay(h.launch_date)) + 7 * RELATIVE_WEEKS;
    if (baselineFrom === null || week < baselineFrom) baselineFrom = week;
  }

  function busy(group, week) {
    if (measure === "raw") return count(group, week) - 1;
    let usual = 0;
    for (let k = 1; k <= RELATIVE_WEEKS; k++) usual += count(group, week - 7 * k);
    usual /= RELATIVE_WEEKS;
    return round2((count(group, week) - 1) / Math.max(usual, 1));
  }

  const out = { measure };
  for (const group of GROUPS) {
    const sample = chosen
      .filter(
        (h) =>
          groupOf(h) === group && h.reviews_30d != null && (measure === "raw" || weekOf.get(h) >= baselineFrom),
      )
      .map((h) => [busy(group, weekOf.get(h)), h.reviews_30d]);
    out[group] = terciles(sample, minGroup);
  }
  out.matched = perGroup(chosen);
  out.total = perGroup(history.filter((h) => PANEL_TYPES.includes(h.launch_type)));
  return out;
}

// Where quiet ends and normal ends: equal busy values stay in one part, and each
// cut is the value whose running total is closest to a third (then two thirds)
// of the games; ties go to the lower value.
export function cutPoints(busy) {
  if (!busy.length) return null;
  const counts = new Map();
  for (const b of busy) counts.set(b, (counts.get(b) ?? 0) + 1);
  const running = [];
  let total = 0;
  for (const [value, n] of [...counts].sort((a, b) => a[0] - b[0])) {
    total += n;
    running.push([value, total]);
  }
  const closest = (rows, target) =>
    rows.reduce((best, vt) => {
      const d = Math.abs(vt[1] - target);
      const bd = Math.abs(best[1] - target);
      return d < bd || (d === bd && vt[0] < best[0]) ? vt : best;
    });
  const c1 = closest(running, total / 3)[0];
  const later = running.filter((vt) => vt[0] > c1);
  const c2 = later.length ? closest(later, (2 * total) / 3)[0] : c1;
  return [c1, c2];
}

function terciles(sample, minGroup) {
  const split = { quiet: [], normal: [], busy: [] };
  const cuts = cutPoints(sample.map(([b]) => b));
  if (cuts) {
    for (const row of sample) split[row[0] <= cuts[0] ? "quiet" : row[0] <= cuts[1] ? "normal" : "busy"].push(row);
  }
  const result = { games: sample.length, shown: true, parts: {} };
  for (const name of PARTS) {
    const rows = split[name];
    if (rows.length < Math.max(minGroup, 1)) {
      result.shown = false;
      result.parts[name] = { games: rows.length };
      continue;
    }
    const reviews = rows.map(([, r]) => r);
    const busy = rows.map(([b]) => b);
    result.parts[name] = {
      games: rows.length,
      busy_min: busy.reduce((a, b) => Math.min(a, b)),
      busy_max: busy.reduce((a, b) => Math.max(a, b)),
      median: percentile(reviews, 0.5),
      p75: percentile(reviews, 0.75),
      p90: percentile(reviews, 0.9),
    };
  }
  return result;
}
