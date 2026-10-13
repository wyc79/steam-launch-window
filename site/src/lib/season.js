// What history says about a week of the year: the site's "typical for this time
// of year" numbers. A port of analysis/season.py, which is the reference and
// documents the rules; test/golden.test.js checks this file against it.
// Weeks are "YYYY-MM-DD" Mondays; ratios are objects keyed by them.

import { makeDay, parts, toDay, toIso, weekday, weekStartDay } from "./dates.js";
import { PANEL_TYPES, RELATIVE_WEEKS, selected } from "./heatmap.js";

export const EVENT_TYPES = ["next_fest", "seasonal_sale", "regional_holiday"];
export const EVENT_WINDOW = 4; // weeks before and after an event that its pattern covers
export const MIN_YEARS = 3; // an estimate needs this many past years
export const MIN_SD = 0.05; // floor, so a near-constant estimate cannot take all the weight
const YEAR = /\s*\b(19|20)\d{2}\b/g;

// Each week's launches divided by the average week in the RELATIVE_WEEKS before it,
// for weeks with a full baseline, through the last complete week of the data.
export function weeklyRatios(history, { selection = [], mode = "and", languages = [], group = "paid" } = {}) {
  if (!history.length) return {};
  const counts = new Map();
  for (const h of selected(history, { selection, mode, languages })) {
    if (PANEL_TYPES.includes(h.launch_type) && !!h.free === (group === "free")) {
      const week = weekStartDay(toDay(h.launch_date));
      counts.set(week, (counts.get(week) ?? 0) + 1);
    }
  }
  let first = Infinity;
  let newest = -Infinity;
  for (const h of history) {
    const day = toDay(h.launch_date);
    first = Math.min(first, weekStartDay(day));
    newest = Math.max(newest, day);
  }
  const last = weekStartDay(newest) - (weekday(newest) === 6 ? 0 : 7); // the newest week may be partial
  const out = {};
  for (let week = first + 7 * RELATIVE_WEEKS; week <= last; week += 7) {
    let usual = 0;
    for (let k = 1; k <= RELATIVE_WEEKS; k++) usual += counts.get(week - 7 * k) ?? 0;
    usual /= RELATIVE_WEEKS;
    out[toIso(week)] = (counts.get(week) ?? 0) / (usual || 1);
  }
  return out;
}

// an event's name without its year: the name of its series
export function seriesName(name) {
  return name.replace(YEAR, "").trim();
}

// Start weeks of each recurring event, by name without the year.
export function eventSeries(events) {
  const series = {};
  for (const e of events) {
    if (EVENT_TYPES.includes(e.type)) {
      (series[seriesName(e.name)] ??= []).push(weekStartDay(toDay(e.start)));
    }
  }
  return Object.fromEntries(
    Object.entries(series).map(([name, weeks]) => [name, weeks.sort((a, b) => a - b).map(toIso)]),
  );
}

function part(name, values) {
  if (values.length < MIN_YEARS) return null;
  // shifted by the first value, so equal values give exactly that value and an sd of 0,
  // as Python's exact statistics.mean and stdev do (otherwise they agree to ~1e-15)
  const shift = values[0];
  const mean = shift + values.reduce((a, v) => a + (v - shift), 0) / values.length;
  const sd = Math.sqrt(values.reduce((a, v) => a + (v - mean) ** 2, 0) / (values.length - 1));
  return { name, mean, sd, years: values.length };
}

// the week in `year` that holds the calendar date of `week`'s Thursday
function sameTime(week, year) {
  const mid = parts(week + 3);
  return weekStartDay(makeDay(year, mid.month, mid.month === 2 ? Math.min(mid.day, 28) : mid.day));
}

// Calendar and event estimates for `week`, and their weighted combination.
export function estimate(week, ratios, series, before) {
  const target = toDay(week);
  const cutoff = toDay(before);
  const past = new Map();
  for (const [w, r] of Object.entries(ratios)) {
    if (toDay(w) < cutoff) past.set(toDay(w), r);
  }
  let calendar = null;
  if (past.size) {
    const weeks = new Set();
    const from = parts(Math.min(...past.keys())).year;
    for (let y = from; y <= parts(cutoff).year; y++) weeks.add(sameTime(target, y));
    calendar = part("calendar", [...weeks].filter((w) => past.has(w) && w !== target).map((w) => past.get(w)));
  }
  const events = [];
  for (const [name, isoStarts] of Object.entries(series)) {
    const starts = isoStarts.map(toDay);
    const near = starts.reduce((best, s) => (Math.abs(target - s) < Math.abs(target - best) ? s : best));
    const offset = Math.floor((target - near) / 7);
    if (Math.abs(offset) > EVENT_WINDOW) continue;
    const values = starts.filter((s) => s !== near && past.has(s + 7 * offset)).map((s) => past.get(s + 7 * offset));
    const p = part(name, values);
    if (p) events.push({ ...p, offset });
  }
  const all = [calendar, ...events].filter(Boolean);
  if (!all.length) return { calendar: null, events: [], expected: null, sd: null };
  const weights = all.map((p) => p.years / Math.max(p.sd, MIN_SD) ** 2);
  const total = weights.reduce((a, b) => a + b, 0);
  return {
    calendar,
    events,
    expected: weights.reduce((a, w, i) => a + w * all[i].mean, 0) / total,
    sd: Math.sqrt(weights.reduce((a, w, i) => a + w * all[i].sd ** 2, 0) / total),
  };
}

// The site's "typical for this time of year" numbers: for each of the `weeks`
// weeks from today's, per group, the expected ratio and spread from the pattern
// of all games in the user's languages, not just the selected tags.
export function outlook(history, events, today, { weeks = 26, languages = [] } = {}) {
  const series = eventSeries(events);
  const first = toIso(weekStartDay(toDay(today)));
  const out = { weeks: Array.from({ length: weeks }, (_, i) => toIso(toDay(first) + 7 * i)) };
  for (const group of ["paid", "free"]) {
    const ratios = weeklyRatios(history, { languages, group });
    out[group] = out.weeks.map((week) => {
      const est = estimate(week, ratios, series, first);
      return {
        expected: est.expected,
        sd: est.sd,
        parts: [est.calendar, ...est.events]
          .filter(Boolean)
          .map((p) => (p.offset === undefined ? p.name : `${p.name} ${p.offset >= 0 ? "+" : ""}${p.offset}`)),
      };
    });
  }
  return out;
}
