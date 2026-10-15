// What history says, from the model (model.json, written by analysis/model.py): the
// launch timing lines for the picked group, from the fit the model calls its
// headline. Sizes are rate ratios with 95% ranges, said as plain percentages.
//
// One rule for advice: an event line says "Avoid ..." only when its range leaves out
// 1.0 and, where the model ran a chance test, the test agrees (p < 0.05). A range
// that leaves out 1.0 without the chance test's support is an "unconfirmed" line,
// not advice; a range that takes in 1.0 is "no clear effect" (US holidays are then
// left out). Weekly competition is described, never given as a penalty. China's
// holidays get one context line, without numbers. A group whose status is not "ok"
// (or no model.json) shows one line, and none of its numbers.

import { numberFormat } from "./format.js";
import { en } from "./strings.js";

const Z95 = 1.959964;
export const CHANCE_P = 0.05; // the chance test must agree at this level for advice
// the holidays that get a line when their range leaves out 1.0; one window a year
export const US_HOLIDAYS = ["us_thanksgiving", "xmas_newyear"];
export const CN_HOLIDAYS = ["cn_spring", "cn_national"];
export const CHINESE = "schinese";
const EPSILON = 1e-9; // so 1 - 0.545 (0.45499...) rounds as the 0.455 it is
export const FEW_GAMES = 100; // a China holiday line says "from few games" under this many

export function clear(e) {
  return e.low > 1 || e.high < 1;
}

// a share as a whole percentage, rounded half up (docs/methods.md uses the same rule)
export function percentOf(x) {
  return Math.floor(x * 100 + 0.5 + EPSILON);
}

export function percent(x, s = en) {
  return numberFormat(s.locale, { style: "percent", maximumFractionDigits: 0 }).format(percentOf(x) / 100);
}

// "37% fewer reviews (24% to 47% fewer)" from a rate ratio and its range
export function change(e, s = en) {
  const t = s.history;
  const fewer = e.rate_ratio < 1;
  const [lo, hi] = fewer ? [1 - e.high, 1 - e.low] : [e.low - 1, e.high - 1];
  return t.change(percent(Math.abs(e.rate_ratio - 1), s), fewer ? t.fewer : t.more, percent(lo, s), percent(hi, s));
}

// Two effects that multiply (a demo, and a demo out by the last Next Fest), when
// model.json has no joint estimate: the range treats them as independent. They share
// the demo games and pull against each other, so the true range is narrower.
export function combine(a, b) {
  const se = (e) => (Math.log(e.high) - Math.log(e.low)) / (2 * Z95);
  const log = Math.log(a.rate_ratio) + Math.log(b.rate_ratio);
  const width = Z95 * Math.hypot(se(a), se(b));
  return { rate_ratio: Math.exp(log), low: Math.exp(log - width), high: Math.exp(log + width) };
}


// the fit the model reads: the follower-controlled one once it is the headline
export function headlineFit(m) {
  return m?.headline === "with_followers" ? m.followers?.with_followers : m?.reviews;
}

export function ready(model, group) {
  const m = model?.[group];
  return !!m && m.status === "ok" && Array.isArray(headlineFit(m)?.effects);
}

// one effect of the headline fit, by key
export function effectOf(m, key) {
  return headlineFit(m)?.effects?.find((e) => e.key === key) ?? null;
}

// The one rule for an event (a sale, a themed fest, a US holiday), shared by the
// lines and the lane tooltips in Competition ahead (eventeffects.js). Returns null (not
// fitted), or { kind, e, years }: "none" when the range takes in 1.0; "advice" when
// it leaves 1.0 out and the chance test agrees (p < 0.05; an event the model ran no
// chance test for counts as agreeing, except a holiday, which then stays unconfirmed);
// otherwise "unconfirmed". years: a holiday's windows (one a year), 0 if unknown.
export function verdict(m, key) {
  const e = effectOf(m, key);
  if (!e) return null;
  if (!clear(e)) return { kind: "none", e, years: 0 };
  const holiday = US_HOLIDAYS.includes(key);
  const p = m.chance_test?.[key]?.p_value ?? e.chance_p ?? null;
  const confirmed = p === null ? !holiday : p < CHANCE_P;
  const years = holiday ? (m.chance_test?.[key]?.windows ?? e.windows ?? 0) : 0;
  return { kind: confirmed ? "advice" : "unconfirmed", e, years };
}

// China's holiday `key` for games with Simplified Chinese (holidays.with_schinese):
// null unless that effect is clear; then its direction, the games behind it, and
// whether the pooled chance test confirms the same direction (p < 0.05).
export function chinaVerdict(m, key) {
  const c = m.holidays?.with_schinese?.[key];
  if (!c || !clear(c)) return null;
  const test = m.chance_test?.[key];
  const fewer = c.rate_ratio < 1;
  const confirmed = !!test && test.p_value < CHANCE_P && test.ratio_alone < 1 === fewer;
  return { key, fewer, confirmed, games: c.games_with ?? null };
}

// Weekly competition from the model's placebo check, as analysis/model.py describes
// it. "General crowding" only when the placebo (the same measure 8 weeks after
// launch) is clear and goes the same way as the launch week. Then, with both in one
// fit: a launch week no longer clear is "small at most; much of it is general
// crowding"; one that stays clear is "a clear effect; part of it is general
// crowding". Otherwise the line only says which way it went.
export function crowdingKind(m, comp) {
  const check = m.checks?.placebo;
  const alone = check?.placebo?.effects?.[0];
  const together = check?.together?.effects?.find((e) => e.key === m.competition_measure);
  const sameWay = alone && alone.rate_ratio < 1 === comp.rate_ratio < 1;
  if (!alone || !together || !clear(alone) || !sameWay) return "none";
  return clear(together) ? "part" : "atMost";
}

export function crowding(m, comp, group, s = en) {
  const t = s.history;
  const kind = crowdingKind(m, comp);
  if (kind === "none") return t.crowdNone(comp.rate_ratio < 1 ? t.fewer : t.more);
  return kind === "part" ? t.crowdPart(s.season[group]) : t.crowdAtMost;
}

// The note under the history panel: busier weeks can look better there because
// stronger games often launch then; then what the model says, from the same rule as
// the competition line. Without a ready model, only the first sentence.
export function busyNote(model, group, s = en) {
  const t = s.history;
  const first = t.busyLooks;
  if (!ready(model, group)) return first;
  const m = model[group];
  const comp = effectOf(m, m.competition_measure);
  if (!comp) return first;
  if (!clear(comp)) return `${first}${t.sentenceSep}${t.busyModel.noEffect}`;
  const kind = crowdingKind(m, comp);
  const said =
    kind === "none" ? t.busyModel.none(comp.rate_ratio < 1 ? t.fewer : t.more) : t.busyModel[kind](s.season[group]);
  return `${first}${t.sentenceSep}${said}`;
}

// China's holidays as one line without numbers: each holiday whose effect for games
// with Simplified Chinese is clear, said for those games, with "from few games" and
// "not confirmed by a chance test" where they apply.
export function chinaLine(m, s = en) {
  const t = s.history;
  const named = CN_HOLIDAYS.map((k) => chinaVerdict(m, k)).filter(Boolean);
  if (!named.length) return t.chinaNone;
  const parts = named.map((v) => {
    const few = v.games !== null && v.games < FEW_GAMES; // said without the number, like the rest
    return t.chinaHoliday(t.chinaNames[v.key], v.fewer ? t.fewer : t.more, few, v.confirmed);
  });
  const windows = named.flatMap((v) => m.holidays?.[v.key] ?? []);
  if (windows.length && windows.every((w) => w.overlaps?.length > 0)) parts.push(t.chinaOverlap);
  return parts.join(t.sentenceSep);
}

// The lines for `group` ("paid" or "free"). languages: the picked ones (China's
// holidays only with Simplified Chinese). Returns { ready: false, text } or
// { ready: true, heading, lines, china, caveat }; china is null or one line.
export function timingLines(model, group, { languages = [] } = {}, s = en) {
  const t = s.history;
  if (!ready(model, group)) return { ready: false, text: t.notReady };
  const m = model[group];
  const effect = (key) => effectOf(m, key);
  const lines = [];

  // an event: advice, unconfirmed, or no clear effect (left out for the holidays)
  const event = (key, avoid, good, holiday = false) => {
    const v = verdict(m, key);
    if (!v) return;
    if (v.kind === "none") {
      if (!holiday) lines.push(t.noEffect(t.names[key]));
      return;
    }
    const fewer = v.e.rate_ratio < 1;
    if (v.kind === "advice") lines.push((fewer ? avoid : good)(change(v.e, s), v.years));
    else lines.push(t.unconfirmed(t.names[key], fewer ? t.fewer : t.more, v.years ? t.years(v.years) : "", t.also[key]));
  };
  event("sale", t.saleAvoid, t.saleGood);
  event("themed_fest", t.festAvoid, t.festGood);

  const demo = effect("demo");
  const fest = effect("demo_last_fest");
  if (fest && !clear(fest)) lines.push(t.noEffect(t.demoFest));
  else if (fest) {
    let text = t.demoVsAfter(change(fest, s));
    if (demo) {
      // the joint estimate from the main fit, when the main fit is the headline
      const joint = m.headline === "with_followers" ? null : (m.demo_with_fest ?? null);
      const both = joint ?? combine(demo, fest);
      // the cautious note goes with a range shown, not with "no clear difference"
      const note = joint ? "" : t.cautious;
      text += `${t.demoAnd}${clear(both) ? `${t.demoVsNone(change(both, s))}${note}` : t.demoAsNone}`;
    }
    const sentence = `${text}${t.sentenceEnd}`;
    lines.push(fest.rate_ratio > 1 ? `${t.demoAdvice}${t.adviceSep}${sentence}` : sentence);
    if (demo && clear(demo)) lines.push(t.demoAfter(change(demo, s)));
  }

  const comp = effect(m.competition_measure);
  if (comp && !clear(comp)) lines.push(t.noEffect(t.competition));
  else if (comp) {
    const niche = t.niche[m.competition_measure] ?? t.niche.competition;
    lines.push(t.competitionLine(crowding(m, comp, group, s), niche));
  }

  for (const key of US_HOLIDAYS) event(key, t.holidays[key], t.holidaysGood[key], true);

  const china = languages.includes(CHINESE) ? chinaLine(m, s) : null;
  return { ready: true, heading: t.timingFor(s.bar[group]), lines, china, caveat: t.caveat };
}
