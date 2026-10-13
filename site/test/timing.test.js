// The launch timing lines from model.json: which lines show for paid and free
// games, the "not ready" line, China's holidays only with Simplified Chinese, and
// the words for a rate ratio and its range.

import { describe, expect, test } from "vitest";
import { en } from "../src/strings.js";
import { change, clear, combine, crowding, ready, timingLines } from "../src/timing.js";

const e = (key, rate_ratio, low, high, extra = {}) => ({ key, rate_ratio, low, high, p: 0.001, ...extra });
const placebo = (alone, real, together) => ({
  measure: "comp_tier_placebo",
  placebo: { effects: [alone] },
  real_same_sample: { effects: [real] },
  together: { effects: together },
});

// numbers from the 2026-10-13 model run
const PAID = {
  status: "ok",
  competition_measure: "comp_tier",
  reviews: {
    effects: [
      e("comp_tier", 0.991, 0.9879, 0.9941),
      e("sale", 0.6343, 0.5326, 0.7553, { windows: 19 }),
      e("demo_last_fest", 1.71, 1.363, 2.145),
      e("themed_fest", 0.5476, 0.4618, 0.6495, { windows: 69 }),
      e("us_thanksgiving", 1.375, 0.7451, 2.539, { windows: 4 }),
      e("xmas_newyear", 1.157, 0.7728, 1.732, { windows: 4 }),
      e("demo", 0.596, 0.4918, 0.7223),
    ],
  },
  checks: {
    placebo: placebo(e("comp_tier_placebo", 0.991, 0.988, 0.994), e("comp_tier", 0.99, 0.987, 0.994), [
      e("comp_tier", 0.994, 0.988, 1.0, { p: 0.05 }),
      e("comp_tier_placebo", 0.996, 0.99, 1.0),
    ]),
  },
  holidays: {
    with_schinese: {
      cn_spring: e("cn_spring_schinese", 0.7087, 0.545, 0.9216),
      cn_national: e("cn_national_schinese", 0.4783, 0.2424, 0.9439),
    },
  },
};
const FREE = {
  status: "ok",
  competition_measure: "competition",
  reviews: {
    effects: [
      e("competition", 0.9515, 0.9376, 0.9656),
      e("sale", 0.8883, 0.6985, 1.13, { windows: 19 }),
      e("demo_last_fest", 1.945, 1.09, 3.473),
      e("themed_fest", 0.9752, 0.6667, 1.426, { windows: 69 }),
      e("us_thanksgiving", 0.4819, 0.3552, 0.6536, { windows: 4 }),
      e("xmas_newyear", 0.5261, 0.3713, 0.7455, { windows: 4 }),
      e("demo", 0.3831, 0.2314, 0.6341),
    ],
  },
  checks: {
    placebo: placebo(e("competition_placebo", 0.947, 0.932, 0.962), e("competition", 0.946, 0.931, 0.961), [
      e("competition", 0.961, 0.943, 0.978, { p: 0.0001 }),
      e("competition_placebo", 0.965, 0.95, 0.98),
    ]),
  },
  holidays: {
    with_schinese: {
      cn_spring: e("cn_spring_schinese", 1.274, 0.3476, 4.665),
      cn_national: e("cn_national_schinese", 0.3935, 0.2562, 0.6044),
    },
  },
};
const MODEL = { paid: PAID, free: FREE };

describe("paid games", () => {
  const v = timingLines(MODEL, "paid");

  test("give advice for sales, themed fests and Next Fest demos, and describe competition", () => {
    expect(v.ready).toBe(true);
    expect(v.heading).toBe("Paid games, compared with otherwise similar launches:");
    expect(v.lines).toEqual([
      "Avoid launching during a Steam seasonal sale: such launches got 37% fewer reviews (24% to 47% fewer).",
      "Avoid a themed fest that matches your tags: such launches got 45% fewer reviews (35% to 54% fewer).",
      "If you have a demo, show it in Next Fest. Launches whose demo was in the last Next Fest got 71% more reviews (36% to 115% more) than those whose demo skipped it, and about as many as launches with no demo.",
      "A demo that skipped Next Fest went with 40% fewer reviews (28% to 51% fewer) than no demo.",
      "Weekly competition: small, mostly general crowding. Each extra launch in your niche and price tier that week: 0.9% fewer reviews (0.6% to 1.2% fewer).",
    ]);
  });

  test("leave out US holidays whose range takes in 1.0", () => {
    expect(v.lines.join(" ")).not.toMatch(/Thanksgiving|Christmas/);
    expect(v.note).toBeNull();
  });

  test("show China's holidays only with Simplified Chinese picked, marked unconfirmed", () => {
    expect(v.china).toBeNull();
    const zh = timingLines(MODEL, "paid", { languages: ["english", "schinese"] });
    expect(zh.china.heading).toMatch(/unconfirmed, not advice/);
    expect(zh.china.lines).toEqual([
      "Spring Festival: 29% fewer reviews (8% to 45% fewer).",
      "National Day: 52% fewer reviews (6% to 76% fewer).",
    ]);
    expect(zh.lines).toEqual(v.lines); // never advice
  });

  test("end with one short caveat", () => {
    expect(v.caveat).toBe(en.history.caveat);
  });
});

describe("free games", () => {
  const v = timingLines(MODEL, "free", { languages: ["schinese"] });

  test("say no clear effect for sales and themed fests, and show the US holidays with their caution", () => {
    expect(v.heading).toBe("Free games, compared with otherwise similar launches:");
    expect(v.lines).toEqual([
      "Steam seasonal sales: no clear effect.",
      "Themed fests for your tags: no clear effect.",
      "If you have a demo, show it in Next Fest. Launches whose demo was in the last Next Fest got 95% more reviews (9% to 247% more) than those whose demo skipped it, and about as many as launches with no demo.",
      "A demo that skipped Next Fest went with 62% fewer reviews (37% to 77% fewer) than no demo.",
      "Weekly competition: mostly general crowding. Each extra launch in your niche that week: 4.8% fewer reviews (3.4% to 6.2% fewer).",
      "Avoid US Thanksgiving to Cyber Monday: such launches got 52% fewer reviews (35% to 64% fewer).",
      "Avoid Christmas to New Year: such launches got 47% fewer reviews (25% to 63% fewer).",
    ]);
    expect(v.note).toBe("The US holiday lines rest on only 4 years each.");
  });

  test("give China's holidays from the Simplified Chinese effect, unclear ones as no clear effect", () => {
    expect(v.china.lines).toEqual(["Spring Festival: no clear effect.", "National Day: 61% fewer reviews (40% to 74% fewer)."]);
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
  ])("%s: one line and no numbers", (_, model) => {
    const v = timingLines(model, "free", { languages: ["schinese"] });
    expect(v).toEqual({ ready: false, text: "Not ready yet." });
    expect(JSON.stringify(v)).not.toMatch(numbers);
  });

  test("the other group still shows", () => {
    expect(ready({ ...MODEL, free: { status: "failed" } }, "paid")).toBe(true);
  });
});

describe("the words", () => {
  test("a range is said from the side of 1.0 the effect is on", () => {
    expect(change(e("x", 0.6343, 0.5326, 0.7553))).toBe("37% fewer reviews (24% to 47% fewer)");
    expect(change(e("x", 1.2, 1.05, 1.4))).toBe("20% more reviews (5% to 40% more)");
    expect(change(e("x", 0.991, 0.9879, 0.9941), en, 1)).toBe("0.9% fewer reviews (0.6% to 1.2% fewer)");
  });

  test("clear means the range leaves out 1.0", () => {
    expect(clear(e("x", 0.9, 0.8, 0.99))).toBe(true);
    expect(clear(e("x", 0.9, 0.8, 1.01))).toBe(false);
    expect(clear(e("x", 1.1, 1.0, 1.3))).toBe(false);
  });

  test("two effects that multiply: the product, with a cautious range", () => {
    const both = combine(e("demo", 0.596, 0.4918, 0.7223), e("demo_last_fest", 1.71, 1.363, 2.145));
    expect(both.rate_ratio).toBeCloseTo(1.0192, 4);
    expect(both.low).toBeLessThan(1);
    expect(both.high).toBeGreaterThan(1);
    // equal widths on the log scale add as a square root of two
    const one = e("a", 1, Math.exp(-0.1), Math.exp(0.1));
    expect(Math.log(combine(one, one).high)).toBeCloseTo(0.1 * Math.SQRT2, 10);
  });

  test("a demo line when Next Fest showed no clear difference", () => {
    const model = {
      paid: { ...PAID, reviews: { effects: [e("demo_last_fest", 1.1, 0.9, 1.3), e("demo", 0.6, 0.5, 0.7)] } },
    };
    expect(timingLines(model, "paid").lines).toEqual(["A demo in Next Fest: no clear effect."]);
  });

  test("competition is only described when the placebo backs it", () => {
    expect(crowding(PAID)).toBe("small, mostly general crowding");
    expect(crowding(FREE)).toBe("mostly general crowding");
    const weak = { checks: { placebo: placebo(e("p", 0.999, 0.99, 1.01), e("c", 0.99, 0.98, 0.995), []) } };
    expect(crowding(weak)).toBeNull();
    expect(crowding({})).toBeNull();
    const lines = timingLines({ paid: { ...PAID, checks: {} } }, "paid").lines;
    expect(lines.at(-1)).toBe(
      "Weekly competition. Each extra launch in your niche and price tier that week: 0.9% fewer reviews (0.6% to 1.2% fewer).",
    );
  });
});
