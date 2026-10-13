// What past launches during an event of the lanes did, for the event block's tooltip
// and its week's label in Competition ahead. The rules are timing.js's, as in What
// history says: a number only for an event whose line is advice (its range leaves
// out 1.0 and the chance test agrees); "(unconfirmed)" without a number for an
// unconfirmed pattern, or a China holiday per timing.chinaVerdict (only with
// Simplified Chinese); nothing otherwise. Nothing is drawn in the lanes themselves.

import { CHINESE } from "./events.js";
import { en } from "./strings.js";
import { chinaVerdict, percent, ready, verdict } from "./timing.js";

// the model's key for a band event (events.js bandEvents), or null
export function eventKey(e) {
  if (e.kind === "seasonal_sale") return "sale";
  if (e.kind === "themed_fest" || e.kind === "next_fest") return e.kind;
  if (e.kind !== "cn_holiday") return null;
  if (/Spring Festival/.test(e.name)) return "cn_spring";
  return /National Day/.test(e.name) ? "cn_national" : null;
}

// One sentence for the event, or null: "Past paid launches during a seasonal sale got
// 37% fewer reviews." model: model.json (null or not ready: nothing).
export function eventEffect(model, group, e, { languages = [] } = {}, s = en) {
  const key = eventKey(e);
  if (!key || !ready(model, group)) return null;
  const t = s.ahead.effect;
  const m = model[group];
  const who = s.season[group];
  if (key === "cn_spring" || key === "cn_national") {
    const v = languages.includes(CHINESE) ? chinaVerdict(m, key) : null;
    return v ? t.china(v.fewer ? s.history.fewer : s.history.more) : null;
  }
  const v = verdict(m, key);
  if (!v || v.kind === "none") return null;
  const fewer = v.e.rate_ratio < 1;
  const dir = fewer ? s.history.fewer : s.history.more;
  if (v.kind === "unconfirmed") return t.unconfirmed(who, t.names[key], dir);
  const pct = percent(Math.abs(v.e.rate_ratio - 1), s);
  return t.advice(who, t.names[key], pct, dir);
}
