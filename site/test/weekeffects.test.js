// "Past launches in a week like this": which weeks get a number, an unconfirmed
// mark or "usual", for paid and free, overlapping events, and a model not ready.

import { describe, expect, test } from "vitest";
import { eventKey, weekEffects } from "../src/weekeffects.js";

const e = (key, rate_ratio, low, high, extra = {}) => ({ key, rate_ratio, low, high, p: 0.001, ...extra });
const chance = (p_value, ratio_alone = 0.8) => ({ p_value, ratio_alone, windows: 4 });
const MODEL = {
  paid: {
    status: "ok",
    headline: "reviews",
    reviews: {
      effects: [
        e("sale", 0.6343, 0.5326, 0.7553),
        e("themed_fest", 0.5476, 0.4618, 0.6495),
        e("next_fest", 1.191, 0.81, 1.75),
        e("us_thanksgiving", 1.375, 0.7451, 2.539),
      ],
    },
    chance_test: { sale: chance(0.001), themed_fest: chance(0.04), next_fest: chance(0.34), us_thanksgiving: chance(0.42) },
    holidays: { with_schinese: { cn_national: e("cn_national_schinese", 0.48, 0.24, 0.94, { games_with: 349 }) } },
  },
  free: {
    status: "ok",
    headline: "reviews",
    reviews: { effects: [e("sale", 0.89, 0.7, 1.13), e("us_thanksgiving", 0.48, 0.36, 0.65)] },
    chance_test: { sale: chance(0.55), us_thanksgiving: chance(0.055) },
  },
};
// weeks from Monday 2026-11-09: a sale Nov 24 to Dec 1 (weeks 2 and 3), a fest for
// "Cozy" Nov 18 to 25 (weeks 1 and 2), Thanksgiving Nov 26 to 30 (weeks 2 and 3), a
// China holiday Nov 10 (week 0), and a fest for other tags
const EVENTS = [
  { name: "Steam Autumn Sale 2026", type: "seasonal_sale", start: "2026-11-24", end: "2026-12-01" },
  { name: "Steam Cozy Fest 2026", type: "themed_fest", start: "2026-11-18", end: "2026-11-25", tags: ["Cozy"] },
  { name: "Steam Racing Fest 2026", type: "themed_fest", start: "2026-12-07", end: "2026-12-14", tags: ["Racing"] },
  { name: "US Thanksgiving to Cyber Monday 2026", type: "regional_holiday", region: "US", start: "2026-11-26", end: "2026-11-30" },
  { name: "China National Day holiday 2026", type: "regional_holiday", region: "CN", start: "2026-11-10", end: "2026-11-11" },
];
const weeks = (group, opts = {}) =>
  weekEffects(MODEL, group, EVENTS, "2026-11-09", 6, { tagNames: ["Cozy"], languages: ["english"], ...opts });

test("events map to the model's keys", () => {
  expect(EVENTS.map(eventKey)).toEqual(["sale", "themed_fest", "themed_fest", "us_thanksgiving", "cn_national"]);
  expect(eventKey({ type: "major_release", name: "x" })).toBeNull();
});

describe("paid", () => {
  const w = weeks("paid");

  test("a number where an advice event falls, usual elsewhere; competition is never a number", () => {
    expect(w.map((x) => [x.kind, x.text])).toEqual([
      ["usual", "usual"],
      ["effect", "0.55x"],
      ["effect", "0.63x 0.55x"],
      ["effect", "0.63x"],
      ["usual", "usual"],
      ["usual", "usual"],
    ]);
    expect(w[1].label).toBe("Past launches in a themed fest matching your tags got 45% fewer reviews (35% to 54% fewer)");
  });

  test("two events in one week are shown side by side, never multiplied", () => {
    expect(w[2].effects.map((x) => x.ratio)).toEqual([0.6343, 0.5476]);
    expect(w[2].label).toBe(
      "Past launches in a Steam seasonal sale got 37% fewer reviews (24% to 47% fewer); Past launches in a themed fest matching your tags got 45% fewer reviews (35% to 54% fewer) (each event on its own, not combined)",
    );
  });

  test("a themed fest for other tags, or no tags picked, does not count", () => {
    expect(weeks("paid", { tagNames: [] })[1].kind).toBe("usual");
  });

  test("China's holidays: an unconfirmed mark only with Simplified Chinese picked", () => {
    expect(w[0].kind).toBe("usual");
    const zh = weeks("paid", { languages: ["schinese"] });
    expect([zh[0].kind, zh[0].text]).toEqual(["unconfirmed", "unconf."]);
    expect(zh[0].label).toBe(
      "An unconfirmed pattern in past launches: in China's National Day holiday (games with Simplified Chinese)",
    );
  });
});

describe("free", () => {
  test("the unconfirmed US holiday gets a mark, the unclear sale nothing", () => {
    const w = weeks("free");
    expect(w.map((x) => x.kind)).toEqual(["usual", "usual", "unconfirmed", "unconfirmed", "usual", "usual"]);
    expect(w[2].text).toBe("unconf.");
    expect(w.every((x) => x.effects.length === 0)).toBe(true);
  });
});

test("a model that is not ready: no row", () => {
  expect(weekEffects({ ...MODEL, free: { status: "unreliable" } }, "free", EVENTS, "2026-11-09", 6)).toBeNull();
  expect(weekEffects(null, "paid", EVENTS, "2026-11-09", 6)).toBeNull();
});
