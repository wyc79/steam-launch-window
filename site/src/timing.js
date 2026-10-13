// What history says, from the model (model.json, written by analysis/model.py): the
// launch timing lines for the picked group. Sizes are rate ratios with 95% ranges,
// said as plain percentages. A line gives a size only when its range leaves out 1.0
// (no change); otherwise it says "no clear effect" or is left out. A group whose
// status is not "ok" (or no model.json) shows one line, and none of its numbers.

import { numberFormat } from "./format.js";
import { en } from "./strings.js";

const Z95 = 1.959964;
// the holidays that get a line when their range leaves out 1.0; they rest on few years
export const US_HOLIDAYS = ["us_thanksgiving", "xmas_newyear"];
export const CN_HOLIDAYS = ["cn_spring", "cn_national"];
export const CHINESE = "schinese";
// the placebo's share of the launch week's effect from which the competition number
// is "mostly general crowding" (analysis/model.py placebo_caveat uses the same)
export const CROWDING = 0.67;

export function clear(e) {
  return e.low > 1 || e.high < 1;
}

function percent(x, s, digits) {
  return numberFormat(s.locale, { style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(x);
}

// "37% fewer reviews (24% to 47% fewer)" from a rate ratio and its range
export function change(e, s = en, digits = 0) {
  const t = s.history;
  const fewer = e.rate_ratio < 1;
  const [lo, hi] = fewer ? [1 - e.high, 1 - e.low] : [e.low - 1, e.high - 1];
  const p = (x) => percent(x, s, digits);
  return t.change(p(Math.abs(e.rate_ratio - 1)), fewer ? t.fewer : t.more, p(lo), p(hi));
}

// Two effects that multiply (a demo, and a demo in the last Next Fest), with a range
// that treats them as independent. The two estimates share the demo games, so they
// pull against each other and the true range is narrower: this one is cautious.
export function combine(a, b) {
  const se = (e) => (Math.log(e.high) - Math.log(e.low)) / (2 * Z95);
  const log = Math.log(a.rate_ratio) + Math.log(b.rate_ratio);
  const width = Z95 * Math.hypot(se(a), se(b));
  return { rate_ratio: Math.exp(log), low: Math.exp(log - width), high: Math.exp(log + width) };
}

// "small, mostly general crowding" from the placebo check: the same measure 8 weeks
// after launch, alone, against the launch week's on the same games, and both in one
// model. Mostly crowding when the placebo is clear, goes the same way and is at
// least CROWDING times as large; small when the launch week, next to the placebo,
// is not clear at p < 0.01 (as the model's own caveat says). Null without the check.
export function crowding(m, s = en) {
  const check = m.checks?.placebo;
  const alone = check?.placebo?.effects?.[0];
  const real = check?.real_same_sample?.effects?.[0];
  if (!alone || !real || !clear(alone)) return null;
  const sameWay = alone.rate_ratio < 1 === real.rate_ratio < 1;
  const size = Math.abs(Math.log(alone.rate_ratio)) / Math.max(Math.abs(Math.log(real.rate_ratio)), 1e-12);
  if (!sameWay || size < CROWDING) return null;
  const together = check.together?.effects?.find((e) => e.key === real.key);
  return together && together.p >= 0.01 ? s.history.crowdSmall : s.history.crowd;
}

export function ready(model, group) {
  const m = model?.[group];
  return !!m && m.status === "ok" && Array.isArray(m.reviews?.effects);
}

// The lines for `group` ("paid" or "free"). languages: the picked ones (China's
// holidays only with Simplified Chinese). Returns { ready: false, text } or
// { ready: true, heading, lines, china, note, caveat }; china is null or
// { heading, lines }, note null or the US holidays' caution.
export function timingLines(model, group, { languages = [] } = {}, s = en) {
  const t = s.history;
  if (!ready(model, group)) return { ready: false, text: t.notReady };
  const m = model[group];
  const effect = (key) => m.reviews.effects.find((e) => e.key === key) ?? null;
  const lines = [];

  const event = (key, name, avoid, good) => {
    const e = effect(key);
    if (!e) return;
    lines.push(!clear(e) ? t.noEffect(name) : (e.rate_ratio < 1 ? avoid : good)(change(e, s)));
  };
  event("sale", t.sale, t.saleAvoid, t.saleGood);
  event("themed_fest", t.fest, t.festAvoid, t.festGood);

  const demo = effect("demo");
  const fest = effect("demo_last_fest");
  if (fest && !clear(fest)) lines.push(t.noEffect(t.demoFest));
  else if (fest) {
    let text = t.demoVsSkipped(change(fest, s));
    if (demo) {
      const both = combine(demo, fest);
      text += `, and ${clear(both) ? t.demoVsNone(change(both, s)) : t.demoAsNone}`;
    }
    lines.push(fest.rate_ratio > 1 ? `${t.demoAdvice} ${text}.` : `${text}.`);
    if (demo && clear(demo)) lines.push(t.demoSkipped(change(demo, s)));
  }

  const comp = effect(m.competition_measure);
  if (comp && !clear(comp)) lines.push(t.noEffect(t.competition));
  else if (comp) {
    const where = t.perLaunch[m.competition_measure] ?? t.perLaunch.competition;
    lines.push(t.competitionLine(crowding(m, s), where, change(comp, s, 1)));
  }

  const holidays = US_HOLIDAYS.map(effect).filter((e) => e && clear(e));
  for (const e of holidays) lines.push((e.rate_ratio < 1 ? t.holidays : t.holidaysGood)[e.key](change(e, s)));
  const years = Math.max(...holidays.map((e) => e.windows ?? 0));
  const note = holidays.length && years > 0 ? t.holidayYears(years) : null;

  let china = null;
  const combined = m.holidays?.with_schinese;
  if (languages.includes(CHINESE) && combined) {
    const rows = CN_HOLIDAYS.filter((k) => combined[k]).map((k) => {
      const e = combined[k];
      return t.chinaChange(t.chinaLine[k], clear(e) ? change(e, s) : t.noClear);
    });
    if (rows.length) china = { heading: t.china, lines: rows };
  }

  return { ready: true, heading: t.timingFor(s.bar[group]), lines, china, note, caveat: t.caveat };
}
