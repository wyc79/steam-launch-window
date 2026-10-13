// "Past launches in a week like this": a row in Competition ahead that brings the
// model's event effects (What history says) to the weeks they fall in, for the
// picked group. The rules are timing.js's: a number only for an event whose line is
// advice (its range leaves out 1.0 and the chance test agrees); a mark for an event
// whose pattern is unconfirmed (or a China holiday, per timing.chinaVerdict, only
// with Simplified Chinese); otherwise "about usual". Weekly competition is not
// turned into a number. An event counts in a week it covers at least one day of,
// as in the events lanes (events.js). The effect is for launching during the event.

import { CHINESE, inWeek, shows, span } from "./events.js";
import { formatRatio } from "./heatview.js";
import { toDay } from "./lib/dates.js";
import { en } from "./strings.js";
import { change, chinaVerdict, ready, verdict } from "./timing.js";

// the model's key for an event in events.json, or null (not in the model)
export function eventKey(e) {
  if (e.type === "seasonal_sale") return "sale";
  if (e.type === "themed_fest") return "themed_fest";
  if (e.type === "next_fest") return "next_fest";
  if (e.type !== "regional_holiday") return null;
  if (e.region === "CN") {
    if (/Spring Festival/.test(e.name)) return "cn_spring";
    return /National Day/.test(e.name) ? "cn_national" : null;
  }
  if (/^US Thanksgiving/.test(e.name)) return "us_thanksgiving";
  if (/^Christmas to New Year/.test(e.name)) return "xmas_newyear";
  return null;
}

// does the event count for this selection: themed fests matching a picked tag and
// China's holidays with Simplified Chinese (events.js shows), the rest always
function counts(e, key, picked) {
  if (key === "themed_fest" || key === "cn_spring" || key === "cn_national") return shows(e, picked);
  return true;
}

// For `weeks` weeks from the Monday `first`: null when the group's model is not
// ready; else one entry a week, { kind: "effect" | "unconfirmed" | "usual", text,
// label, effects }. effects lists each advice event in the week on its own (two in
// one week are shown side by side, never multiplied).
export function weekEffects(model, group, events, first, weeks, { tagNames = [], languages = [] } = {}, s = en) {
  if (!ready(model, group)) return null;
  const m = model[group];
  const a = s.ahead.like;
  const picked = { tagNames, languages };
  const keyed = (events ?? [])
    .map((e) => ({ e, key: eventKey(e) }))
    .filter(({ e, key }) => key && counts(e, key, picked))
    .map(({ e, key }) => {
      const [from, to] = span(e);
      return { key, from, to };
    });
  const begin = toDay(first);
  return Array.from({ length: weeks }, (_, i) => {
    const keys = [...new Set(keyed.filter((x) => inWeek(x, begin + 7 * i)).map((x) => x.key))];
    const effects = [];
    const unconfirmed = [];
    for (const key of keys) {
      if (key === "cn_spring" || key === "cn_national") {
        if (languages.includes(CHINESE) && chinaVerdict(m, key)) unconfirmed.push(key);
        continue;
      }
      const v = verdict(m, key);
      if (v?.kind === "advice") {
        const text = a.ratio(formatRatio(v.e.rate_ratio, s));
        effects.push({ key, ratio: v.e.rate_ratio, text, label: a.effect(a.names[key], change(v.e, s)) });
      } else if (v?.kind === "unconfirmed") unconfirmed.push(key);
    }
    if (effects.length) {
      const label = effects.map((x) => x.label).join("; ") + (effects.length > 1 ? ` ${a.apart}` : "");
      return { kind: "effect", text: effects.map((x) => x.text).join(" "), label, effects };
    }
    if (unconfirmed.length) {
      const label = a.unconfirmedLabel(unconfirmed.map((k) => a.names[k]).join(", "));
      return { kind: "unconfirmed", text: a.unconfirmed, label, effects };
    }
    return { kind: "usual", text: a.usual, label: a.usualLabel, effects };
  });
}
