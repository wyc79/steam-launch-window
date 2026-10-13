// Trends: the quarterly launches (lib/trends.js quarterly) as text and bar heights,
// for the picked group and view. Nothing is computed here but sums for the line
// over the chart, the scale and formatting.

import { formatNumber } from "./count.js";
import { formatDate } from "./heatview.js";
import { numberFormat } from "./format.js";
import { toDay, toIso } from "./lib/dates.js";
import { en } from "./strings.js";

export const VIEWS = ["share", "count", "cumulative"];
export const MIN_COMPARE = 20; // the line over the chart compares two windows only with this many launches in each
const STEPS = [1, 2, 2.5, 5, 10];
const TICKS = 4; // about this many steps up the axis

// The views the switch offers: with no tags the share is 100% everywhere, so it is left out.
export const viewsFor = (tags) => (tags.length ? VIEWS : VIEWS.filter((v) => v !== "share"));

// A share as a percentage: one decimal, or two significant digits under 1%
// ("0.04%"), so a small niche does not read as 0.0%.
export function formatShare(x, s = en) {
  const opts =
    x > 0 && x < 0.01
      ? { style: "percent", maximumSignificantDigits: 2 }
      : { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 };
  return numberFormat(s.locale, opts).format(x);
}

// The axis: a round step (1, 2, 2.5 or 5 times a power of ten; whole numbers for
// counts) and the top it reaches, at or above `max`. Returns the tick values from 0.
export function niceTicks(max, whole) {
  if (!(max > 0)) return whole ? [0, 1] : [0, 0.01];
  const raw = max / TICKS;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = STEPS.map((m) => m * mag).find((x) => x >= raw && (!whole || Number.isInteger(x))) ?? 10 * mag;
  const top = Math.ceil(max / step - 1e-9) * step;
  const out = [];
  for (let i = 0; i * step <= top + step / 2; i++) out.push(Number((i * step).toPrecision(12)));
  return out;
}

// The tick labels: counts as numbers; shares with as many decimals as the step
// needs (0.025% steps get three), so no two ticks read the same.
export function tickTexts(ticks, whole, s = en) {
  if (whole) return ticks.map((x) => formatNumber(x, s));
  const exact = (d) => ticks.every((x) => Math.abs(Math.round(x * 100 * 10 ** d) - x * 100 * 10 ** d) < 1e-6);
  const digits = [0, 1, 2, 3, 4, 5].find(exact) ?? 6;
  return ticks.map((x) => numberFormat(s.locale, { style: "percent", maximumFractionDigits: digits }).format(x));
}

// "in English", "in English or Simplified Chinese", "in 3 languages", "in any language"
export function langsText(languages, s = en) {
  const sec = s.sections.season;
  const names = languages.map((c) => s.languages[c] ?? c);
  return names.length > 2 ? sec.nLangs(names.length) : sec.langs(names);
}

const cap = (x) => x.charAt(0).toUpperCase() + x.slice(1);

function quarterName(q, s) {
  const t = s.trends;
  const name = t.quarter(q.year, q.q);
  if (!q.partial) return q.recent ? t.recentName(name) : name;
  if (!q.days) return t.justStarted(name);
  return t.soFarName(name, formatDate(q.start, s), formatDate(toIso(toDay(q.start) + q.days - 1), s));
}

// an average a quarter: whole numbers, one decimal under 10 (so 0.5 is not "0")
const perQuarter = (x, s) =>
  numberFormat(s.locale, { maximumFractionDigits: x < 10 ? 1 : 0 }).format(x < 10 ? x : Math.round(x));

// q: quarterly's result. view: the view picked (share, count or cumulative); with no
// tags there is no share (viewsFor), so "share" shows the counts. Returns { view,
// empty, bars, ticks, years, recent, summary, few, partial }: one bar per quarter with its
// height (0 to 1 of the axis; `over` when the quarter under way runs off a scale set by
// the full quarters), its label and short name; `recent` the first recent quarter and
// how many (their tags may still change).
export function trendView(q, group, view, s = en, { tags = [], languages = [] } = {}) {
  const t = s.trends;
  const shown = viewsFor(tags).includes(view) ? view : "count";
  const rows = q[group];
  const word = s.season[group]; // "paid", "free"
  const f = (n) => formatNumber(n, s);
  const value = (r) => (shown === "share" ? (r.share ?? 0) : shown === "count" ? r.niche : r.cumulative);
  const whole = shown !== "share";
  // a few days of a new quarter can set a share far off; a running total never jumps
  const scaled = rows.filter((_, i) => shown === "cumulative" || !q.quarters[i].partial);
  const ticks = niceTicks(Math.max(0, ...scaled.map(value)), whole);
  const top = ticks.at(-1);

  const bars = q.quarters.map((qq, i) => {
    const r = rows[i];
    const name = quarterName(qq, s);
    let label;
    if (!r.all) label = t.none(name, word);
    else if (shown === "cumulative") label = t.since(name, f(r.cumulative), word, f(r.niche));
    else if (tags.length) label = t.of(name, f(r.niche), f(r.all), word, formatShare(r.share, s));
    else label = t.plain(name, f(r.niche), r.niche, word);
    const over = value(r) > top;
    return {
      year: qq.year,
      short: `Q${qq.q}`,
      partial: qq.partial,
      recent: qq.recent,
      value: Math.min(1, value(r) / top),
      over,
      label: over ? t.offScale(label) : label,
    };
  });

  const years = [];
  q.quarters.forEach((qq, i) => {
    if (years.at(-1)?.year === qq.year) years.at(-1).span += 1;
    else years.push({ year: qq.year, from: i, span: 1 });
  });

  // the first year against the four full quarters before the recent ones
  const settled = q.quarters.map((qq, i) => [qq, rows[i]]).filter(([qq]) => !qq.recent);
  const first = settled.filter(([qq]) => qq.year === settled[0]?.[0].year).map(([, r]) => r);
  const base = settled.slice(-4);
  const last = base.map(([, r]) => r);
  const named = ([qq]) => t.quarter(qq.year, qq.q);
  const span = base.length ? t.span(named(base[0]), named(base.at(-1))) : "";
  const sum = (list, k) => list.reduce((a, r) => a + r[k], 0);
  const langs = langsText(languages, s);
  const who = tags.length ? cap(t.who(word, langs)) : t.whoAll(word, langs);
  let summary = null;
  let few = false; // too few launches in a window to compare them
  if (settled.length >= 8) {
    few = shown !== "cumulative" && (sum(first, "niche") < MIN_COMPARE || sum(last, "niche") < MIN_COMPARE);
    if (shown === "cumulative") summary = t.summaryCumulative(who, f(rows.at(-1).cumulative));
    else if (few) summary = t.tooFew(MIN_COMPARE);
    else if (shown === "share") {
      const share = (list) => formatShare(sum(list, "niche") / sum(list, "all"), s);
      summary = t.summaryShare(word, langs, share(first), f(sum(first, "niche")), share(last), f(sum(last, "niche")), span);
    } else {
      const avg = (list) => perQuarter(sum(list, "niche") / list.length, s);
      summary = t.summaryCount(who, avg(first), avg(last), span);
    }
  }

  const now = q.quarters.at(-1);
  const texts = tickTexts(ticks, whole, s);
  return {
    view: shown,
    empty: !rows.some((r) => r.niche) ? t.empty : null,
    bars,
    ticks: ticks.map((x, i) => ({ at: x / top, text: texts[i] })),
    years,
    recent: { from: bars.findIndex((b) => b.recent), span: bars.filter((b) => b.recent).length },
    summary,
    few,
    partial: now?.partial
      ? now.days
        ? t.partial(t.quarter(now.year, now.q), f(now.days), f(now.length))
        : t.partialStart(t.quarter(now.year, now.q))
      : null,
  };
}
