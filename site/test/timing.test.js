// The launch timing lines from model.json: one rule for advice (the range leaves out
// 1.0 and the chance test agrees), unconfirmed lines, "not ready", competition
// described from the fit with the placebo, China's holidays as one line without
// numbers, the demo lines, the headline fit, and the rounding of percentages.

import { describe, expect, test } from "vitest";
import { en } from "../src/strings.js";
import { busyNote, change, clear, combine, crowding, percentOf, ready, timingLines } from "../src/timing.js";

const e = (key, rate_ratio, low, high, extra = {}) => ({ key, rate_ratio, low, high, p: 0.001, ...extra });
const placebo = (alone, real, together) => ({
  measure: `${real.key}_placebo`,
  placebo: { effects: [alone] },
  real_same_sample: { effects: [real] },
  together: { effects: together },
});
const chance = (p_value, ratio_alone, windows) => ({ p_value, ratio_alone, windows });
const holidays = (with_schinese, overlapped = true) => ({
  cn_spring: [1, 2, 3, 4, 5].map((y) => ({ name: `Spring ${y}`, overlaps: overlapped ? ["a sale"] : [] })),
  cn_national: [1, 2, 3, 4].map((y) => ({ name: `National ${y}`, overlaps: ["a fest"] })),
  with_schinese,
});

// numbers from the 2026-10-13 model run
const PAID = {
  status: "ok",
  headline: "reviews",
  competition_measure: "comp_tier",
  reviews: {
    effects: [
      e("comp_tier", 0.991, 0.9879, 0.9941),
      e("sale", 0.6343, 0.5326, 0.7553),
      e("demo_last_fest", 1.71, 1.363, 2.145),
      e("themed_fest", 0.5476, 0.4618, 0.6495),
      e("cn_spring", 0.6274, 0.4584, 0.8586),
      e("cn_national", 0.4399, 0.2888, 0.67),
      e("us_thanksgiving", 1.375, 0.7451, 2.539),
      e("xmas_newyear", 1.157, 0.7728, 1.732),
      e("demo", 0.596, 0.4918, 0.7223),
    ],
  },
  chance_test: {
    sale: chance(0.000999, 0.7458, 19),
    themed_fest: chance(0.04096, 0.5591, 69),
    cn_spring: chance(0.08092, 0.7017, 5),
    cn_national: chance(0.006993, 0.5097, 4),
    us_thanksgiving: chance(0.4186, 1.259, 4),
    xmas_newyear: chance(0.6094, 1.112, 4),
  },
  checks: {
    placebo: placebo(e("comp_tier_placebo", 0.991, 0.988, 0.994), e("comp_tier", 0.99, 0.987, 0.994), [
      e("comp_tier", 0.9941, 0.9878, 1.0),
      e("comp_tier_placebo", 0.9955, 0.9907, 1.0),
    ]),
  },
  holidays: holidays({
    cn_spring: e("cn_spring_schinese", 0.7087, 0.545, 0.9216, { games_with: 531 }),
    cn_national: e("cn_national_schinese", 0.4783, 0.2424, 0.9439, { games_with: 349 }),
  }),
};
const FREE = {
  status: "ok",
  headline: "reviews",
  competition_measure: "competition",
  reviews: {
    effects: [
      e("competition", 0.9515, 0.9376, 0.9656),
      e("sale", 0.8883, 0.6985, 1.13),
      e("demo_last_fest", 1.945, 1.09, 3.473),
      e("themed_fest", 0.9752, 0.6667, 1.426),
      e("cn_spring", 2.248, 0.9346, 5.407),
      e("cn_national", 1.328, 0.6296, 2.803),
      e("us_thanksgiving", 0.4819, 0.3552, 0.6536),
      e("xmas_newyear", 0.5261, 0.3713, 0.7455),
      e("demo", 0.3831, 0.2314, 0.6341),
    ],
  },
  chance_test: {
    sale: chance(0.5514, 0.9342, 19),
    themed_fest: chance(0.961, 0.9796, 69),
    cn_spring: chance(0.08991, 1.585, 5),
    cn_national: chance(0.8172, 1.084, 4),
    us_thanksgiving: chance(0.05495, 0.5364, 4),
    xmas_newyear: chance(0.09391, 0.6171, 4),
  },
  checks: {
    placebo: placebo(e("competition_placebo", 0.947, 0.932, 0.962), e("competition", 0.946, 0.931, 0.961), [
      e("competition", 0.9608, 0.9434, 0.9784),
      e("competition_placebo", 0.9654, 0.9478, 0.9834),
    ]),
  },
  holidays: holidays({
    cn_spring: e("cn_spring_schinese", 1.274, 0.3476, 4.665, { games_with: 45 }),
    cn_national: e("cn_national_schinese", 0.3935, 0.2562, 0.6044, { games_with: 36 }),
  }),
};
const MODEL = { paid: PAID, free: FREE };

const PAID_LINES = [
  "Avoid launching during a Steam seasonal sale: such launches got 37% fewer reviews (24% to 47% fewer).",
  "Avoid a themed fest that matches your game's tags: such launches got 45% fewer reviews (35% to 54% fewer).",
  "If you have a demo, have it out before Next Fest. Launches whose demo was out by the last Next Fest got 71% more reviews (36% to 115% more) than those whose demo came out after it, and no clear difference from launches with no demo.",
  "A demo that came out after the last Next Fest went with 40% fewer reviews (28% to 51% fewer) than no demo.",
  "Weekly competition: small at most; much of it is general crowding (a niche here is games with similar tags, a shared language and the same price tier, not just your tags).",
];

describe("paid games", () => {
  const v = timingLines(MODEL, "paid");

  test("advice for sales and themed fests (the chance test agrees), the demo line, competition described", () => {
    expect(v.ready).toBe(true);
    expect(v.heading).toBe("Paid games, compared with otherwise similar launches:");
    expect(v.lines).toEqual(PAID_LINES);
    expect(v.caveat).toBe(en.history.caveat);
  });

  test("competition has no per-launch percentage", () => {
    expect(v.lines.at(-1)).not.toMatch(/\d/);
  });

  test("China's holidays: one line without numbers, only with Simplified Chinese", () => {
    expect(v.china).toBeNull();
    const zh = timingLines(MODEL, "paid", { languages: ["english", "schinese"] });
    expect(zh.china).toBe(
      "Spring Festival (unconfirmed): fewer reviews for games with Simplified Chinese in past years, not confirmed by a chance test. National Day (unconfirmed): fewer reviews for games with Simplified Chinese in past years. Every one of these holiday windows overlapped a Steam sale or fest.",
    );
    expect(zh.china).not.toMatch(/\d/);
    expect(zh.lines).toEqual(PAID_LINES); // never advice
  });

  test("without the joint estimate, a shown range is marked cautious; \"no clear difference\" is not", () => {
    const model = { paid: { ...PAID, reviews: { effects: [e("demo_last_fest", 1.2, 1.1, 1.3), e("demo", 0.5, 0.45, 0.55)] } } };
    expect(timingLines(model, "paid").lines[0]).toMatch(/than launches with no demo \(a cautious range\)\.$/);
    expect(timingLines(MODEL, "paid").lines[2]).toMatch(/no clear difference from launches with no demo\.$/);
  });

  test("the joint demo estimate is used when model.json has it", () => {
    const joint = { ...PAID, demo_with_fest: e("demo_with_fest", 1.25, 1.05, 1.49) };
    expect(timingLines({ paid: joint }, "paid").lines[2]).toBe(
      "If you have a demo, have it out before Next Fest. Launches whose demo was out by the last Next Fest got 71% more reviews (36% to 115% more) than those whose demo came out after it, and 25% more reviews (5% to 49% more) than launches with no demo.",
    );
  });
});

describe("free games", () => {
  const v = timingLines(MODEL, "free", { languages: ["schinese"] });

  test("no clear effect for sales and themed fests; US holidays unconfirmed, not advice", () => {
    expect(v.heading).toBe("Free games, compared with otherwise similar launches:");
    expect(v.lines).toEqual([
      "Steam seasonal sales: no clear effect.",
      "Themed fests for your game's tags: no clear effect.",
      "If you have a demo, have it out before Next Fest. Launches whose demo was out by the last Next Fest got 95% more reviews (9% to 247% more) than those whose demo came out after it, and no clear difference from launches with no demo.",
      "A demo that came out after the last Next Fest went with 62% fewer reviews (37% to 77% fewer) than no demo.",
      "Weekly competition: a clear effect for free games; part of it is general crowding (a niche here is games with similar tags and a shared language, not just your tags).",
      "US Thanksgiving to Cyber Monday: fewer reviews in past years (4 years), not confirmed by a chance test; the week also falls in Steam's Autumn Sale most years.",
      "Christmas to New Year: fewer reviews in past years (4 years), not confirmed by a chance test; the week also falls in Steam's Winter Sale every year.",
    ]);
    expect(v.lines.join(" ")).not.toMatch(/Avoid (US|Christmas)/);
  });

  test("a US holiday the chance test confirms is advice, with its years", () => {
    const confirmed = { ...FREE, chance_test: { ...FREE.chance_test, us_thanksgiving: chance(0.01, 0.53, 4) } };
    expect(timingLines({ free: confirmed }, "free").lines).toContain(
      "Avoid US Thanksgiving to Cyber Monday: in 4 years, such launches got 52% fewer reviews (35% to 64% fewer).",
    );
  });

  test("China's holidays: each holiday from the effect for games with Simplified Chinese", () => {
    // Spring Festival is not clear for those games: not named; National Day is, from 36 games (no number shown)
    expect(v.china).toBe(
      "National Day (unconfirmed): fewer reviews for games with Simplified Chinese in past years, from few games, not confirmed by a chance test. Every one of these holiday windows overlapped a Steam sale or fest.",
    );
    const none = { ...FREE, holidays: holidays({ cn_spring: e("x", 1.1, 0.8, 1.4) }) };
    expect(timingLines({ free: none }, "free", { languages: ["schinese"] }).china).toBe(
      "China holidays (unconfirmed): no clear dip for games with Simplified Chinese in past launches.",
    );
  });

  test("a US holiday without a chance-test row stays unconfirmed and never says 0 years", () => {
    const { us_thanksgiving, ...rest } = FREE.chance_test;
    const lines = timingLines({ free: { ...FREE, chance_test: rest } }, "free").lines;
    expect(lines).toContain(
      "US Thanksgiving to Cyber Monday: fewer reviews in past years, not confirmed by a chance test; the week also falls in Steam's Autumn Sale most years.",
    );
    expect(lines.join(" ")).not.toMatch(/0 years/);
  });
});

describe("not ready", () => {
  const numbers = /\d/;
  test.each([
    ["no model.json", null],
    ["unreliable", { ...MODEL, free: { status: "unreliable", recounted_share: 0.4, caveats: ["x"] } }],
    ["failed", { ...MODEL, free: { status: "failed", error: "ValueError: boom" } }],
    ["unreliable with numbers left in", { ...MODEL, free: { ...FREE, status: "unreliable" } }],
    ["a group missing", { paid: PAID }],
    ["headline fit missing", { ...MODEL, free: { ...FREE, headline: "with_followers", followers: {} } }],
  ])("%s: one line and no numbers", (_, model) => {
    const v = timingLines(model, "free", { languages: ["schinese"] });
    expect(v).toEqual({ ready: false, text: "Not ready yet." });
    expect(JSON.stringify(v)).not.toMatch(numbers);
  });

  test("the other group still shows", () => {
    expect(ready({ ...MODEL, free: { status: "failed" } }, "paid")).toBe(true);
  });
});

test("the headline fit is read: the follower-controlled one once it is the headline", () => {
  const followers = { with_followers: { effects: [e("sale", 1.2, 1.1, 1.3)] } };
  const v = timingLines({ paid: { ...PAID, headline: "with_followers", followers } }, "paid");
  expect(v.lines).toEqual(["Launches during a Steam seasonal sale got 20% more reviews (10% to 30% more)."]);
});

describe("the words", () => {
  test("a range is said from the side of 1.0 the effect is on", () => {
    expect(change(e("x", 0.6343, 0.5326, 0.7553))).toBe("37% fewer reviews (24% to 47% fewer)");
    expect(change(e("x", 1.2, 1.05, 1.4))).toBe("20% more reviews (5% to 40% more)");
  });

  test("percentages round half up, also where floating point lands just under a half", () => {
    expect(1 - 0.545).toBeLessThan(0.455);
    expect(percentOf(1 - 0.545)).toBe(46);
    expect(percentOf(0.2447)).toBe(24);
    expect(percentOf(0.125)).toBe(13);
    expect(change(e("x", 0.7087, 0.545, 0.9216))).toBe("29% fewer reviews (8% to 46% fewer)");
  });

  test("clear means the range leaves out 1.0", () => {
    expect(clear(e("x", 0.9, 0.8, 0.99))).toBe(true);
    expect(clear(e("x", 0.9, 0.8, 1.01))).toBe(false);
    expect(clear(e("x", 1.1, 1.0, 1.3))).toBe(false);
  });

  test("two effects that multiply, without a joint estimate: the product, with a cautious range", () => {
    const both = combine(e("demo", 0.596, 0.4918, 0.7223), e("demo_last_fest", 1.71, 1.363, 2.145));
    expect(both.rate_ratio).toBeCloseTo(1.0192, 4);
    expect(both.low).toBeLessThan(1);
    expect(both.high).toBeGreaterThan(1);
    const one = e("a", 1, Math.exp(-0.1), Math.exp(0.1));
    expect(Math.log(combine(one, one).high)).toBeCloseTo(0.1 * Math.SQRT2, 10);
  });

  test("a demo line when the demo before Next Fest showed no clear difference", () => {
    const model = {
      paid: { ...PAID, reviews: { effects: [e("demo_last_fest", 1.1, 0.9, 1.3), e("demo", 0.6, 0.5, 0.7)] } },
    };
    expect(timingLines(model, "paid").lines).toEqual(["A demo out before Next Fest: no clear effect."]);
  });

  test("competition: from the fit with the placebo", () => {
    const comp = e("comp_tier", 0.99, 0.98, 0.995);
    expect(crowding(PAID, comp, "paid")).toBe("small at most; much of it is general crowding");
    expect(crowding(FREE, comp, "free")).toBe("a clear effect for free games; part of it is general crowding");
    // a placebo that goes the other way from the launch week: no "general crowding"
    const other = { ...PAID, checks: { placebo: { ...PAID.checks.placebo, placebo: { effects: [e("p", 1.01, 1.005, 1.02)] } } } };
    expect(crowding(other, comp, "paid")).toBe("launches in busier weeks of their niche got fewer reviews");
    const weak = { competition_measure: "c", checks: { placebo: placebo(e("p", 0.999, 0.99, 1.01), e("c", 0.99, 0.98, 0.995), [e("c", 0.99, 0.98, 0.995)]) } };
    expect(crowding(weak, comp, "paid")).toBe("launches in busier weeks of their niche got fewer reviews");
    expect(crowding({}, comp, "paid")).toBe("launches in busier weeks of their niche got fewer reviews");
  });
});

describe("the note under the history panel", () => {
  const first = "Busier weeks can look better here because stronger games often launch then.";
  test("says what the model says about busier weeks, from the competition rule", () => {
    expect(busyNote(MODEL, "paid")).toBe(`${first} Comparing similar games, a busier week goes with slightly fewer reviews at most.`);
    expect(busyNote(MODEL, "free")).toBe(`${first} Comparing similar free games, a busier week goes with clearly fewer reviews.`);
  });

  test("only the first sentence without a ready model; no clear effect when competition is not clear", () => {
    expect(busyNote(null, "paid")).toBe(first);
    expect(busyNote({ free: { status: "unreliable" } }, "free")).toBe(first);
    const unclear = { paid: { ...PAID, reviews: { effects: [e("comp_tier", 0.999, 0.99, 1.01)] } } };
    expect(busyNote(unclear, "paid")).toBe(`${first} Comparing similar games, a busier week shows no clear effect.`);
  });
});
