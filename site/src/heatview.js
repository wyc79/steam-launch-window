// What section 01 shows, as plain data: the heatmap's weeks, rows and cells with
// their text, shade steps and screen reader labels. The numbers come from
// lib/heatmap.js (heatmapRows, normalized); this file only picks and formats them,
// so ui/ahead.js has nothing left to decide.

import { formatNumber } from "./count.js";
import { toDay, toIso } from "./lib/dates.js";
import { normalized } from "./lib/heatmap.js";
import { en } from "./strings.js";
import { weekEvents } from "./events.js";

// Shade steps of the normalized view: a value's step is how many of these it
// reaches, so 0 is under 0.1 and 7 is 3 or more. From 1.0 (a usual week) on, the
// shade turns dark: light weeks are quieter than usual, dark ones busier.
export const CUTS = [0.1, 0.25, 0.5, 1, 1.5, 2, 3];
export const NEAR_WEEKS = 4; // weeks more than this many out are faded: dates still being set
export const PARTS = ["exact", "spread", "year"];

export function step(value, cuts) {
  let i = 0;
  while (i < cuts.length && value >= cuts[i]) i++;
  return i;
}

// Raw counts are shaded with the same steps times the combination's usual week
// (the last row), so the two views agree for it; without a usual week, times half
// the biggest part shown.
export function rawCuts(rows, group) {
  let unit = rows.at(-1).typical?.[group] ?? 0;
  if (!unit) {
    let most = 0;
    for (const row of rows) for (const c of row[group]) most = Math.max(most, c.exact, c.spread, c.year);
    unit = most / 2 || 1;
  }
  return CUTS.map((c) => c * unit);
}

// "0" only when there is nothing; small values keep one decimal ("0.0", "1.2");
// 10 and more are whole ("12", "1,204"). `whole` for counts of whole games.
export function formatValue(value, s = en, whole = false) {
  if (whole || value >= 10) return formatNumber(Math.round(value), s);
  if (value === 0) return "0";
  return new Intl.NumberFormat(s.locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
}

// a usual week's launches: like formatValue, but two digits under 1 ("0.38", "0.019")
export function formatUsual(value, s = en) {
  if (value >= 1) return formatValue(value, s);
  return new Intl.NumberFormat(s.locale, { maximumSignificantDigits: 2 }).format(value);
}

// a legend step's lower end: "0", "0.25", "1.0"; raw counts as formatValue
export function formatCut(value, s = en, raw = false) {
  if (raw || value === 0) return formatValue(value, s);
  return new Intl.NumberFormat(s.locale, { minimumFractionDigits: 1, maximumFractionDigits: 2 }).format(value);
}

const dateFormat =(s, opts) => new Intl.DateTimeFormat(s.locale, { ...opts, timeZone: "UTC" });

export function formatDate(iso, s = en) {
  return dateFormat(s, { month: "short", day: "numeric" }).format(toDay(iso) * 86400000);
}

export function rowLabel(tags, mode, names, s = en) {
  if (!tags.length) return s.ahead.allGames;
  if (tags.length === 1) return names.get(tags[0]) ?? String(tags[0]);
  return s.ahead.combo[mode];
}

// The weeks across the top: date, month (only where it changes), this week, far
// weeks, and the band's events in each.
export function weekHeads(weeks, band, s = en) {
  const month = dateFormat(s, { month: "short" });
  let last = null;
  return weeks.map((iso, i) => {
    const m = month.format(toDay(iso) * 86400000);
    const head = {
      iso,
      date: formatDate(iso, s),
      to: formatDate(toIso(toDay(iso) + 6), s),
      day: String(+iso.slice(8, 10)),
      month: m === last ? null : m,
      current: i === 0,
      far: i > NEAR_WEEKS,
      events: weekEvents(band, iso),
    };
    last = m;
    return head;
  });
}

export function eventText(e, s = en) {
  return s.ahead.eventName(e.name, e.unconfirmed ? s.ahead.unconfirmed : e.estimate ? s.ahead.estimate : null);
}

// rows: heatmapRows' result (with history). Returns { weeks, cuts, rows, empty,
// sometime } for the picked group; raw: counts instead of "1.0 = a usual week";
// year: with the year-only part.
export function buildView(rows, { group, raw = false, year = false, mode = "and", names = new Map(), band = [], s = en }) {
  const a = s.ahead;
  const weeks = weekHeads(rows[0].weeks, band, s);
  const cuts = raw ? rawCuts(rows, group) : CUTS;
  const parts = year ? PARTS : PARTS.slice(0, 2);
  const out = rows.map((row) => {
    const label = rowLabel(row.tags, mode, names, s);
    const usual = row.typical?.[group] ?? 0;
    const norm = raw ? null : normalized(row)?.[group];
    const counts = !raw && !norm; // normalized view, but no usual week to compare with
    const cells = row[group].map((cell, i) => {
      const values = norm ? norm[i] : cell;
      const shown = parts.map((part) => {
        const value = values[part];
        return {
          part,
          value,
          text: formatValue(value, s, (raw || counts) && part === "exact"),
          step: counts ? 0 : step(value, cuts),
        };
      });
      const w = weeks[i];
      const said = [
        shown.map((p) => a.cellPart(a.partNames[p.part], p.text)).join(", ") +
          " " +
          (raw || counts ? a.unitRaw : a.unitNormal),
      ];
      if (w.far) said.push(a.far);
      if (w.events.length) said.push(a.events(w.events.map((e) => eventText(e, s)).join(", ")));
      return { parts: shown, label: a.cell(label, w.date, said.join(". ")) };
    });
    return {
      tags: row.tags,
      label,
      usual: usual ? a.usual(formatUsual(usual, s)) : a.noUsual,
      cells,
      matched: row.matched[group],
    };
  });
  let empty = null;
  if (out.every((r) => !r.matched)) empty = a.empty;
  else if (!out.at(-1).matched) empty = a.emptyCombo;
  return { weeks, cuts, parts, rows: out, empty, sometime: sometimeLines(rows.at(-1), group, s) };
}

// "Sometime in 2027: 2,631 games", one per year, then "Later: ..." (heatmap's sometime)
export function sometimeLines(row, group, s = en) {
  const a = s.ahead;
  const lines = Object.entries(row.sometime)
    .filter(([, g]) => g[group].games > 0)
    .map(([year, g]) => {
      const games = a.games(formatNumber(g[group].games, s), g[group].games);
      return year === "later" ? a.later(games) : a.sometime(year, games);
    });
  return lines.length ? lines : [a.noSometime];
}
