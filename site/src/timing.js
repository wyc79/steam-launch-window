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
export const EVENTS = ["sale", "themed_fest"];
// the holidays that get a line when their range leaves out 1.0; one window a year
export const US_HOLIDAYS = ["us_thanksgiving", "xmas_newyear"];
export const CN_HOLIDAYS = ["cn_spring", "cn_national"];
export const CHINESE = "schinese";
const EPSILON = 1e-9; // so 1 - 0.545 (0.45499...) rounds as the 0.455 it is

export function clear(e) {
  return e.low > 1 || e.high < 1;
}

// a share as a whole percentage, rounded half up (docs/methods.md uses the same rule)
export function percentOf(x) {
  return Math.floor(x * 100 + 0.5 + EPSILON);
}

function percent(x, s) {
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

// Weekly competition from the model's placebo check, as analysis/model.py describes
// it: with the placebo (the same measure 8 weeks after launch) in the same fit, a
// launch week that is no longer clear is "small at most; much of it is general
// crowding"; one that stays clear is "small; part of it is general crowding". Without
// a clear placebo the line only says which way it went.
export function crowding(m, comp, s = en) {
  const t = s.history;
  const check = m.checks?.placebo;
  const alone = check?.placebo?.effects?.[0];
  const together = check?.together?.effects?.find((e) => e.key === m.competition_measure);
  if (!alone || !together || !clear(alone)) return t.crowdNone(comp.rate_ratio < 1 ? t.fewer : t.more);
  return clear(together) ? t.crowdPart : t.crowdAtMost;
}

// China's holidays as one line without numbers: "fewer" when the pooled chance test
// says so for either holiday (p < 0.05) or both main effects (games without
// Simplified Chinese) are clearly below 1.0, and neither is clearly above it.
export function chinaLine(m, effect, s = en) {
  const mains = CN_HOLIDAYS.map(effect).filter(Boolean);
  const tests = CN_HOLIDAYS.map((k) => m.chance_test?.[k]).filter((x) => x && "p_value" in x);
  const below = (e) => clear(e) && e.rate_ratio < 1;
  const fewer =
    !mains.some((e) => clear(e) && e.rate_ratio > 1) &&
    (tests.some((x) => x.ratio_alone < 1 && x.p_value < CHANCE_P) || (mains.length === 2 && mains.every(below)));
  const combined = CN_HOLIDAYS.map((k) => m.holidays?.with_schinese?.[k]).filter(Boolean);
  const both = mains.length === 2 && mains.every(below) && combined.length === 2 && combined.every(below);
  const windows = CN_HOLIDAYS.flatMap((k) => m.holidays?.[k] ?? []);
  const overlapped = windows.length > 0 && windows.every((w) => w.overlaps?.length > 0);
  return s.history.china(fewer, fewer && both, fewer && overlapped);
}

// The lines for `group` ("paid" or "free"). languages: the picked ones (China's
// holidays only with Simplified Chinese). Returns { ready: false, text } or
// { ready: true, heading, lines, china, caveat }; china is null or one line.
export function timingLines(model, group, { languages = [] } = {}, s = en) {
  const t = s.history;
  if (!ready(model, group)) return { ready: false, text: t.notReady };
  const m = model[group];
  const effects = headlineFit(m).effects;
  const effect = (key) => effects.find((e) => e.key === key) ?? null;
  const chanceP = (key, e) => m.chance_test?.[key]?.p_value ?? e.chance_p ?? null;
  const windows = (key, e) => m.chance_test?.[key]?.windows ?? e.windows ?? 0;
  const lines = [];

  // an event: advice, unconfirmed, or no clear effect (left out for the holidays)
  const event = (key, avoid, good, holiday = false) => {
    const e = effect(key);
    if (!e) return;
    if (!clear(e)) {
      if (!holiday) lines.push(t.noEffect(t.names[key]));
      return;
    }
    const p = chanceP(key, e);
    const n = holiday ? windows(key, e) : 0; // a holiday has one window a year
    if (p === null || p < CHANCE_P) lines.push((e.rate_ratio < 1 ? avoid : good)(change(e, s), n));
    else lines.push(t.unconfirmed(t.names[key], e.rate_ratio < 1 ? t.fewer : t.more, n ? t.years(n) : "", t.also[key]));
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
      const note = joint ? "" : t.cautious;
      text += `, and ${clear(both) ? t.demoVsNone(change(both, s)) : t.demoAsNone}${note}`;
    }
    lines.push(fest.rate_ratio > 1 ? `${t.demoAdvice} ${text}.` : `${text}.`);
    if (demo && clear(demo)) lines.push(t.demoAfter(change(demo, s)));
  }

  const comp = effect(m.competition_measure);
  if (comp && !clear(comp)) lines.push(t.noEffect(t.competition));
  else if (comp) lines.push(t.competitionLine(crowding(m, comp, s), t.niche[m.competition_measure] ?? t.niche.competition));

  for (const key of US_HOLIDAYS) event(key, t.holidays[key], t.holidaysGood[key], true);

  const china = languages.includes(CHINESE) ? chinaLine(m, effect, s) : null;
  return { ready: true, heading: t.timingFor(s.bar[group]), lines, china, caveat: t.caveat };
}
