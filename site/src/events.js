// The event band above the heatmap's weeks: which events of events.json show for
// a selection, where they fall and which weeks they cover. Not in the Python code.
//
// The rule (docs/phase3-plan.md): Steam seasonal sales and Next Fests always; a
// themed fest when one of the picked tags is among its tags (the model's rule for
// "a themed fest for one of its top tags", analysis/features.py, with the picked
// tags in place of a game's top 10; a fest without tags never shows, as in the
// model); China's holidays only when Simplified Chinese is among the picked
// languages, always marked unconfirmed. Releases and other holidays are left out.

import { toDay } from "./lib/dates.js";

// lanes of the band, top to bottom
export const KINDS = ["seasonal_sale", "next_fest", "themed_fest", "cn_holiday"];
const STEAM_RUN = new Set(["seasonal_sale", "next_fest", "themed_fest"]);
export const STEAM_HOUR = 10; // Steam-run events start and end at 10:00 Pacific (pipeline/events.py)
export const MIN_DAYS = 1; // an event is in a week when it covers at least this many days of it
export const CHINESE = "schinese";

export function kindOf(e) {
  if (e.type === "regional_holiday") return e.region === "CN" ? "cn_holiday" : null;
  return KINDS.includes(e.type) ? e.type : null;
}

// tagNames: the picked tags' names; languages: the picked language codes
export function shows(e, { tagNames = [], languages = [] } = {}) {
  const kind = kindOf(e);
  if (kind === "themed_fest") {
    const picked = new Set(tagNames.map((t) => t.toLowerCase()));
    return (e.tags ?? []).some((t) => picked.has(t.toLowerCase()));
  }
  if (kind === "cn_holiday") return languages.includes(CHINESE);
  return kind !== null;
}

// When the event is in effect, as days since 1970 with fractions: [from, to).
// Steam events run 10:00 to 10:00 Pacific; holidays whole days, end included.
export function span(e) {
  if (STEAM_RUN.has(e.type)) return [toDay(e.start) + STEAM_HOUR / 24, toDay(e.end) + STEAM_HOUR / 24];
  return [toDay(e.start), toDay(e.end) + 1];
}

// "Steam Next Fest October 2026" -> "Next Fest October", for the band's little room
export function shortName(name) {
  return name.replace(/^Steam /, "").replace(/ \d{4}$/, "");
}

// The events to draw for `weeks` weeks from the Monday `first` (an ISO date), in
// time order, each with its lane: { name, short, kind, start, end, from, to,
// unconfirmed, estimate, lane }. `lanes` lists the lanes in use: { kind, row }
// (a second row when events of one kind overlap). `extent(e)`: the day where the
// event stops taking room in its row (default its end; the page adds its label).
export function bandEvents(events, first, weeks, { tagNames = [], languages = [], extent = (e) => e.to } = {}) {
  const begin = toDay(first);
  const stop = begin + 7 * weeks;
  const picked = events
    .filter((e) => shows(e, { tagNames, languages }))
    .map((e) => {
      const [from, to] = span(e);
      const kind = kindOf(e);
      return {
        name: e.name,
        short: shortName(e.name),
        kind,
        start: e.start,
        end: e.end,
        from,
        to,
        unconfirmed: kind === "cn_holiday",
        estimate: e.confidence === "low" && kind !== "cn_holiday",
      };
    })
    .filter((e) => e.to > begin && e.from < stop)
    .sort((a, b) => a.from - b.from || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  // per kind, each event goes in the first row whose last event has ended
  const ends = new Map(KINDS.map((k) => [k, []]));
  for (const e of picked) {
    const rows = ends.get(e.kind);
    let row = rows.findIndex((end) => end <= e.from);
    if (row < 0) row = rows.length;
    rows[row] = extent(e);
    e.row = row;
  }
  const lanes = KINDS.flatMap((kind) => ends.get(kind).map((_, row) => ({ kind, row })));
  for (const e of picked) e.lane = lanes.findIndex((l) => l.kind === e.kind && l.row === e.row);
  return { events: picked, lanes };
}

// The events covering at least MIN_DAYS of the week starting on `monday` (ISO), so
// a Steam event that ends at 10:00 on a Monday is not counted in that week too.
export function weekEvents(band, monday) {
  const start = toDay(monday);
  return band.filter((e) => Math.min(e.to, start + 7) - Math.max(e.from, start) >= MIN_DAYS);
}
