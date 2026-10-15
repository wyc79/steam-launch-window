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
import { en } from "./strings.js";

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

// "Steam Next Fest October 2026" -> "Next Fest October", for the lanes' little room
export function shortName(name) {
  return name.replace(/^Steam /, "").replace(/ \d{4}$/, "");
}

// An event's name (or a series' name, without the year) in the page's language,
// else in English. short: without "Steam" and the year, for little room.
export function eventName(name, s = en, { short = false } = {}) {
  const year = name.match(/ (\d{4})$/)?.[1];
  const local = s.eventSeries(year ? name.slice(0, -5) : name);
  if (!local) return short ? shortName(name) : name;
  if (short) return local.replace(/\{year\} 年 ?/, "").replace(/^Steam /, "");
  return year ? local.replace("{year}", year) : local.replace(/\{year\} 年 ?/, "");
}

// covers at least MIN_DAYS of the week starting on day `start`, so a Steam event
// that ends at 10:00 on a Monday is not counted in that week too
function inWeek(e, start) {
  return Math.min(e.to, start + 7) - Math.max(e.from, start) >= MIN_DAYS;
}

// The events to draw for `weeks` weeks from the Monday `first` (an ISO date), in
// time order: { name, kind, start, end, from, to, unconfirmed, estimate,
// weeks: [first, last] week index it covers, lane, room }. `lanes` lists the lanes
// in use, { kind, row }: a second row when events of one kind share a week.
// `room` is the week index where the next event in its lane starts (or `weeks`):
// how far its name may run.
export function bandEvents(events, first, weeks, { tagNames = [], languages = [] } = {}) {
  const begin = toDay(first);
  const picked = [];
  for (const e of events) {
    if (!shows(e, { tagNames, languages })) continue;
    const [from, to] = span(e);
    const kind = kindOf(e);
    const covered = [];
    for (let i = 0; i < weeks; i++) if (inWeek({ from, to }, begin + 7 * i)) covered.push(i);
    if (!covered.length) continue;
    picked.push({
      name: e.name,
      kind,
      start: e.start,
      end: e.end,
      from,
      to,
      unconfirmed: kind === "cn_holiday",
      estimate: e.confidence === "low" && kind !== "cn_holiday",
      weeks: [covered[0], covered.at(-1)],
    });
  }
  picked.sort((a, b) => a.from - b.from || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  // per kind, each event goes in the first row whose last event ended in an earlier week
  const rows = new Map(KINDS.map((k) => [k, []]));
  for (const e of picked) {
    const lasts = rows.get(e.kind);
    let row = lasts.findIndex((last) => last < e.weeks[0]);
    if (row < 0) row = lasts.length;
    lasts[row] = e.weeks[1];
    e.row = row;
  }
  const lanes = KINDS.flatMap((kind) => rows.get(kind).map((_, row) => ({ kind, row })));
  for (const e of picked) e.lane = lanes.findIndex((l) => l.kind === e.kind && l.row === e.row);
  for (const e of picked) {
    const next = picked.find((x) => x.lane === e.lane && x.weeks[0] > e.weeks[1]);
    e.room = next ? next.weeks[0] : weeks;
  }
  return { events: picked, lanes };
}

// The band's events in the week starting on `monday` (ISO)
export function weekEvents(band, monday) {
  const start = toDay(monday);
  return band.filter((e) => inWeek(e, start));
}

