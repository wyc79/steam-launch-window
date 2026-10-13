// What Competition ahead shows, as plain data: the heatmap's weeks, rows and cells
// with their text, shade steps and screen reader labels. The numbers come from
// lib/heatmap.js (heatmapRows, normalized); this file only picks and formats them,
// so ui/ahead.js has nothing left to decide.

import { formatNumber } from "./count.js";
import { weekEvents } from "./events.js";
import { dateFormat, numberFormat } from "./format.js";
import { toDay, toIso } from "./lib/dates.js";
import { normalized, TYPICAL_WEEKS } from "./lib/heatmap.js";
import { en } from "./strings.js";

// Shade steps: a value's step is how many of these it reaches, so 0 is under 0.1
// and 7 is 3 or more (times a typical week). From 1.0 on the shade turns dark:
// light weeks are quieter than a typical week, dark ones busier.
export const CUTS = [0.1, 0.25, 0.5, 1, 1.5, 2, 3];
export const NEAR_WEEKS = 4; // weeks more than this many out are faded: dates still being set
export const PARTS = ["exact", "spread", "year"];
// A row whose typical week has fewer launches than this shows plain counts,
// unshaded: one launch more or less would swing its ratio wildly.
export const MIN_TYPICAL = 1;
const SMALL = 0.05; // under this a value would read "0.0": it shows "<0.1"

export function step(value, cuts = CUTS) {
  let i = 0;
  while (i < cuts.length && value >= cuts[i]) i++;
  return i;
}

const oneDecimal = (s) => numberFormat(s.locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// The value as it is shown: whole from 9.95 on (or for whole games), one decimal
// below that; exact zero stays 0 and tiny values stay as they are ("<0.1").
export function shownValue(value, whole = false) {
  if (whole || value >= 10 - SMALL) return Math.round(value);
  if (value < SMALL) return value;
  return Math.round(value * 10) / 10;
}

// "0" only when there is nothing; "<0.1" for a little; "1.2"; "12", "1,204".
export function formatValue(value, s = en, whole = false) {
  if (whole || value >= 10 - SMALL) return formatNumber(Math.round(value), s);
  if (value === 0) return "0";
  if (value < SMALL) return s.ahead.below(oneDecimal(s).format(0.1));
  return oneDecimal(s).format(value);
}

// formatValue read aloud: "under 0.1" instead of "<0.1"
export function spokenValue(value, s = en, whole = false) {
  if (!whole && value > 0 && value < SMALL) return s.ahead.under(oneDecimal(s).format(0.1));
  return formatValue(value, s, whole);
}


// a legend step's lower end: "0", "0.25", "1.0"
export function formatCut(value, s = en) {
  if (value === 0) return "0";
  return numberFormat(s.locale, { minimumFractionDigits: 1, maximumFractionDigits: 2 }).format(value);
}

export function formatDate(iso, s = en) {
  return dateFormat(s.locale, { month: "short", day: "numeric" }).format(toDay(iso) * 86400000);
}

export function rowLabel(tags, mode, names, s = en) {
  if (!tags.length) return s.ahead.allGames;
  if (tags.length === 1) return names.get(tags[0]) ?? String(tags[0]);
  return s.ahead.combo[mode];
}

// The weeks across the top: date, this week, far weeks, and the band's events in each.
export function weekHeads(weeks, band, s = en) {
  return weeks.map((iso, i) => ({
    iso,
    date: formatDate(iso, s),
    to: formatDate(toIso(toDay(iso) + 6), s),
    current: i === 0,
    far: i > NEAR_WEEKS,
    events: weekEvents(band, iso),
  }));
}

export function eventText(e, s = en) {
  return s.ahead.eventName(e.name, e.unconfirmed ? s.ahead.unconfirmed : e.estimate ? s.ahead.estimate : null);
}

// rows: heatmapRows' result (with history); band: bandEvents' events. Returns
// { weeks, parts, rows, empty, sometime, anyCounts } for the picked group. raw:
// numbers are games instead of "1.0 = as many as a typical week"; the shades stay
// the same (each row against its own typical week). year: with the year-only part.
export function buildView(rows, { group, raw = false, year = false, mode = "and", names = new Map(), band = [], s = en }) {
  const a = s.ahead;
  const weeks = weekHeads(rows[0].weeks, band, s);
  const parts = year ? PARTS : PARTS.slice(0, 2);
  const out = rows.map((row) => {
    const label = rowLabel(row.tags, mode, names, s);
    const typical = row.typical?.[group] ?? 0;
    const counts = typical < MIN_TYPICAL; // too few past launches to compare with
    const norm = counts ? null : normalized(row)[group];
    const games = raw || counts; // the numbers shown are games
    const cells = row[group].map((cell, i) => {
      const shown = parts.map((part) => {
        const whole = games && part === "exact";
        const value = games ? cell[part] : norm[i][part];
        return {
          part,
          value,
          text: formatValue(value, s, whole),
          spoken: spokenValue(value, s, whole),
          // the shade follows the normalized number as shown, so raw counts change only the text
          step: counts ? 0 : step(shownValue(norm[i][part])),
        };
      });
      const w = weeks[i];
      const said = [
        `${shown.map((p) => a.cellPart(a.partNames[p.part], p.spoken)).join(", ")} ${games ? a.unitRaw : a.unitNormal}`,
      ];
      if (w.far) said.push(a.far);
      if (w.events.length) said.push(a.events(w.events.map((e) => eventText(e, s)).join(", ")));
      return { parts: shown, label: a.cell(label, w.date, said.join(". ")) };
    });
    return {
      tags: row.tags,
      label,
      counts,
      note: counts ? a.fewLaunches(Math.round(typical * TYPICAL_WEEKS)) : a.typical(formatValue(typical, s)),
      cells,
      matched: row.matched[group],
    };
  });
  let empty = null;
  if (out.every((r) => !r.matched)) empty = a.empty;
  else if (!out.at(-1).matched) empty = a.emptyCombo;
  const last = out.at(-1);
  return {
    weeks,
    parts,
    rows: out,
    empty,
    anyCounts: out.some((r) => r.counts),
    sometime: { row: last.label, lines: sometimeLines(rows.at(-1), group, s) },
  };
}

// "2.0", "1.3", "0.69": a share ratio to two significant digits
export function formatRatio(ratio, s = en) {
  return numberFormat(s.locale, { minimumSignificantDigits: 2, maximumSignificantDigits: 2 }).format(ratio);
}

// The niche trend lines, "Cozy: 2.0x its share of past launches among upcoming
// games.", for the rows (buildView's) whose trend (numbers.trend, one per row, null
// for all games) is clear for the picked group.
export function trendLines(rows, trends, group, s = en) {
  return rows.flatMap((r, i) => {
    const t = trends[i]?.[group];
    return t?.clear ? [s.trend.line(r.label, formatRatio(t.ratio, s))] : [];
  });
}

// "sometime in 2027: 2,631 games", one per year, then "later: ..." (heatmap's
// sometime), for one row
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
