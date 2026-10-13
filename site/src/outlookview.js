// Typical for this time of year: the seasonal outlook (lib/season.js outlook) as
// text and bar positions, for the picked group. Each week says what its estimate
// rests on: the same week in past years, and the events near it ("2 weeks after
// Next Fest October"), the parts season.estimate combined.

import { CHINESE, kindOf, shortName, weekEvents } from "./events.js";
import { dateFormat, numberFormat } from "./format.js";
import { eventText, formatDate } from "./heatview.js";
import { parts as dayParts, toDay, toIso } from "./lib/dates.js";
import { EVENT_TYPES, seriesName } from "./lib/season.js";
import { en } from "./strings.js";

export const MIN_SCALE = 0.25; // the bars' scale reaches at least 1.0 plus or minus this

const two = (x, s) => numberFormat(s.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(x);

// recurring event series name -> kind (events.js kindOf), from events.json
export function seriesKinds(events) {
  const out = new Map();
  for (const e of events ?? []) if (EVENT_TYPES.includes(e.type)) out.set(seriesName(e.name), kindOf(e));
  return out;
}

// One part of an estimate as words: "calendar" or "Steam Next Fest October +2".
// China's holidays only with Simplified Chinese picked (marked unconfirmed); null otherwise.
export function partText(part, kinds, languages, s = en) {
  const t = s.season;
  if (part === "calendar") return t.calendar;
  const m = part.match(/^(.*) ([+-]\d+)$/);
  if (!m) return part;
  const china = kinds.get(m[1]) === "cn_holiday";
  if (china && !languages.includes(CHINESE)) return null;
  const name = china ? `${shortName(m[1])} (${t.unconfirmed})` : shortName(m[1]);
  const offset = +m[2];
  if (offset === 0) return t.at(name);
  return offset > 0 ? t.after(offset, name) : t.before(-offset, name);
}

// outlook: season.outlook's result; band: bandEvents' events for the same weeks.
// Returns { weeks, scale } where each week has its dates, value, spread, what it
// rests on, the band's events, and bar positions (-1 to 1 around 1.0, by `scale`).
export function outlookView(outlook, group, { events = [], band = [], languages = [] } = {}, s = en) {
  const t = s.season;
  const kinds = seriesKinds(events);
  const rows = outlook[group];
  let scale = MIN_SCALE;
  for (const o of rows) {
    if (o.expected === null) continue;
    scale = Math.max(scale, Math.abs(o.expected + o.sd - 1), Math.abs(Math.max(0, o.expected - o.sd) - 1));
  }
  scale = Math.ceil(scale * 20) / 20;
  const monthName = dateFormat(s.locale, { month: "short" });
  const weeks = outlook.weeks.map((iso, i) => {
    const o = rows[i];
    const day = toDay(iso);
    const { month, day: dom } = dayParts(day);
    const week = s.ahead.week(formatDate(iso, s), formatDate(toIso(day + 6), s));
    const has = o.expected !== null;
    const lo = has ? Math.max(0, o.expected - o.sd) : null;
    const hi = has ? o.expected + o.sd : null;
    const value = has ? two(o.expected, s) : t.none;
    const spread = has ? t.spread(two(lo, s), two(hi, s)) : null;
    const said = o.parts.map((p) => partText(p, kinds, languages, s)).filter(Boolean);
    const drivers = said.length ? t.drivers(said.join("; ")) : null;
    const weekBand = weekEvents(band, iso);
    return {
      iso,
      week,
      date: formatDate(iso, s),
      day: String(dom),
      month: i === 0 || month !== dayParts(day - 7).month ? monthName.format(day * 86400000) : null,
      current: i === 0,
      value,
      spread,
      drivers,
      events: weekBand.map((e) => eventText({ ...e, name: e.short }, s)),
      eventsFull: weekBand.map((e) => eventText(e, s)),
      bar: has ? { v: (o.expected - 1) / scale, lo: (lo - 1) / scale, hi: (hi - 1) / scale } : null,
      label: t.option(week, has ? t.usually(value) : t.noneSaid, spread, drivers),
      detail: t.detail(week, has ? t.usually(value) : t.noneSaid, spread),
    };
  });
  return { weeks, scale };
}
