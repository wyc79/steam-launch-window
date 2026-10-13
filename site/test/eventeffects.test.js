// What past launches during a lane's event did, for its tooltip and its week's label:
// a number only for advice events, "(unconfirmed)" without a number, nothing else.

import { describe, expect, test } from "vitest";
import { eventEffect, eventKey } from "../src/eventeffects.js";

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
      ],
    },
    chance_test: { sale: chance(0.001), themed_fest: chance(0.04), next_fest: chance(0.34) },
    holidays: { with_schinese: { cn_national: e("cn_national_schinese", 0.48, 0.24, 0.94, { games_with: 349 }) } },
  },
  free: {
    status: "ok",
    headline: "reviews",
    reviews: { effects: [e("sale", 0.85, 0.75, 0.95)] },
    chance_test: { sale: chance(0.2) },
  },
};
const SALE = { kind: "seasonal_sale", name: "Steam Winter Sale 2026" };
const FEST = { kind: "themed_fest", name: "Steam Cozy Fest 2026" };
const NEXT = { kind: "next_fest", name: "Steam Next Fest October 2026" };
const NATIONAL = { kind: "cn_holiday", name: "China National Day holiday 2026" };
const SPRING = { kind: "cn_holiday", name: "China Spring Festival holiday 2027" };

test("lane events map to the model's keys", () => {
  expect([SALE, FEST, NEXT, NATIONAL, SPRING].map(eventKey)).toEqual([
    "sale",
    "themed_fest",
    null, // Next Fest: section 01 has no line for it
    "cn_national",
    "cn_spring",
  ]);
});

describe("paid", () => {
  test("advice events get their size, as section 01 says it", () => {
    expect(eventEffect(MODEL, "paid", SALE)).toBe("Past paid launches during a seasonal sale got 37% fewer reviews.");
    expect(eventEffect(MODEL, "paid", FEST)).toBe(
      "Past paid launches during a themed fest matching their tags got 45% fewer reviews.",
    );
  });

  test("no clear effect: nothing", () => {
    expect(eventEffect(MODEL, "paid", NEXT)).toBeNull();
  });

  test("China's holidays only with Simplified Chinese, unconfirmed and without a number", () => {
    expect(eventEffect(MODEL, "paid", NATIONAL)).toBeNull();
    expect(eventEffect(MODEL, "paid", NATIONAL, { languages: ["schinese"] })).toBe(
      "Past launches of games with Simplified Chinese during this holiday: fewer reviews (unconfirmed).",
    );
    expect(eventEffect(MODEL, "paid", SPRING, { languages: ["schinese"] })).toBeNull(); // not clear for those games
  });
});

test("free: a pattern the chance test does not confirm says so, without a number", () => {
  expect(eventEffect(MODEL, "free", SALE)).toBe("Past free launches during a seasonal sale: fewer reviews (unconfirmed).");
});

test("a model that is not ready, or none: nothing", () => {
  expect(eventEffect({ ...MODEL, free: { status: "unreliable" } }, "free", SALE)).toBeNull();
  expect(eventEffect(null, "paid", SALE)).toBeNull();
  expect(eventEffect(undefined, "paid", SALE)).toBeNull();
});
