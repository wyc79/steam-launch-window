// What history says: the history panel (lib/heatmap.js historyPanel) as text, for
// the picked group. Nothing is computed here but formatting and the bars' lengths.

import { formatNumber } from "./count.js";
import { numberFormat } from "./format.js";
import { MIN_GROUP } from "./lib/heatmap.js";
import { en } from "./strings.js";

export const PARTS = ["quiet", "normal", "busy"];

// a week's busy value: other launches (raw) or times the usual week, 2 decimals
export function formatBusy(value, measure, s = en) {
  if (measure === "raw") return formatNumber(value, s);
  return numberFormat(s.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

const reviews = (x, s) => formatNumber(Math.round(x), s);

// panel: historyPanel's result. Returns { shown: false, text } when the panel is
// hidden, else { shown: true, intro, rows, cuts, read }: one row per part with its
// text and its bars as shares of the largest 90th percentile. tags: the picked tags
// (none: the intro speaks of all games, not "games like yours").
export function panelView(panel, group, s = en, { tags = [] } = {}) {
  const t = s.history;
  const g = panel[group];
  if (!g.shown) return { shown: false, text: g.games ? t.tooFew(formatNumber(MIN_GROUP, s)) : t.none };
  const measure = panel.measure;
  const top = Math.max(...PARTS.map((p) => g.parts[p].p90)) || 1;
  const rows = PARTS.map((name) => {
    const p = g.parts[name];
    return {
      part: name,
      name: t.parts[name],
      range: t.range(formatBusy(p.busy_min, measure, s), formatBusy(p.busy_max, measure, s)),
      p75: reviews(p.p75, s),
      p90: reviews(p.p90, s),
      median: reviews(p.median, s),
      games: formatNumber(p.games, s),
      bars: { p75: p.p75 / top, p90: p.p90 / top, median: p.median / top },
    };
  });
  const quiet = formatBusy(g.parts.quiet.busy_max, measure, s);
  const busy = formatBusy(g.parts.normal.busy_max, measure, s);
  return {
    shown: true,
    intro: tags.length
      ? t.panelFor(s.bar[group], formatNumber(g.games, s))
      : t.panelForAll(s.season[group], formatNumber(g.games, s)),
    rows,
    cuts: measure === "raw" ? t.cutsRaw(quiet, busy) : t.cutsRelative(quiet, busy),
    read: t.read,
  };
}
