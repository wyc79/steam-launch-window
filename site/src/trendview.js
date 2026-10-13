// Trends: the quarterly launches (lib/trends.js quarterly) as text and bar heights,
// for the picked group and view. Nothing is computed here but sums for the line
// over the chart, the scale and formatting.

import { formatNumber } from "./count.js";
import { formatDate } from "./heatview.js";
import { numberFormat } from "./format.js";
import { toDay, toIso } from "./lib/dates.js";
import { en } from "./strings.js";

export const VIEWS = ["share", "count", "cumulative"];
const STEPS = [1, 2, 2.5, 5, 10];
const TICKS = 4; // about this many steps up the axis

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

const tickText = (x, whole, s) =>
  whole ? formatNumber(x, s) : numberFormat(s.locale, { style: "percent", maximumFractionDigits: 2 }).format(x);

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

// q: quarterly's result. view: the view asked for (share, count or cumulative); with
// no tags the share is 100% everywhere, so "share" shows the counts (`fallback`).
// Returns { view, fallback, empty, bars, ticks, years, recent, summary, partial }: one
// bar per quarter with its height (0 to 1 of the axis), its label and short name;
// `recent` the first recent quarter and how many (they may still change).
export function trendView(q, group, view, s = en, { tags = [], languages = [] } = {}) {
  const t = s.trends;
  const fallback = view === "share" && !tags.length;
  const shown = fallback ? "count" : view;
  const rows = q[group];
  const word = s.season[group]; // "paid", "free"
  const f = (n) => formatNumber(n, s);
  const value = (r) => (shown === "share" ? (r.share ?? 0) : shown === "count" ? r.niche : r.cumulative);
  const whole = shown !== "share";
  const ticks = niceTicks(Math.max(0, ...rows.map(value)), whole);
  const top = ticks.at(-1);

  const bars = q.quarters.map((qq, i) => {
    const r = rows[i];
    const name = quarterName(qq, s);
    let label;
    if (!r.all) label = t.none(name, word);
    else if (shown === "cumulative") label = t.since(name, f(r.cumulative), word, f(r.niche));
    else if (tags.length) label = t.of(name, f(r.niche), f(r.all), word, formatShare(r.share, s));
    else label = t.plain(name, f(r.niche), r.niche, word);
    return { year: qq.year, short: `Q${qq.q}`, partial: qq.partial, recent: qq.recent, value: value(r) / top, label };
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
  if (settled.length >= 8) {
    if (shown === "share") {
      const share = (list) => (sum(list, "all") ? formatShare(sum(list, "niche") / sum(list, "all"), s) : "n/a");
      summary = t.summaryShare(word, langs, share(first), share(last), span);
    } else if (shown === "count") {
      const avg = (list) => f(Math.round(sum(list, "niche") / list.length));
      summary = t.summaryCount(who, avg(first), avg(last), span);
    } else {
      summary = t.summaryCumulative(who, f(rows.at(-1).cumulative));
    }
  }

  const now = q.quarters.at(-1);
  return {
    view: shown,
    fallback,
    empty: !rows.some((r) => r.niche) ? t.empty : null,
    bars,
    ticks: ticks.map((x) => ({ at: x / top, text: tickText(x, whole, s) })),
    years,
    recent: { from: bars.findIndex((b) => b.recent), span: bars.filter((b) => b.recent).length },
    summary,
    partial: now?.partial ? t.partial(t.quarter(now.year, now.q), f(now.days), f(now.length)) : null,
  };
}
