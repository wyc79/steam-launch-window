// The seasonal outlook as text: values and spreads with two decimals, what each
// week rests on in words, China's holidays only with Simplified Chinese, the months,
// and bar positions around 1.0.

import { describe, expect, test } from "vitest";
import { bandEvents } from "../src/events.js";
import { MIN_SCALE, outlookView, partText, seriesKinds } from "../src/outlookview.js";
import { zh } from "../src/strings.js";

const EVENTS = [
  { name: "Steam Next Fest October 2026", type: "next_fest", start: "2026-10-19", end: "2026-10-26" },
  { name: "Steam Next Fest October 2025", type: "next_fest", start: "2025-10-13", end: "2025-10-20" },
  { name: "China National Day holiday 2026", type: "regional_holiday", region: "CN", start: "2026-10-01", end: "2026-10-08" },
  { name: "US Thanksgiving to Cyber Monday 2026", type: "regional_holiday", region: "US", start: "2026-11-26", end: "2026-11-30" },
];
const KINDS = seriesKinds(EVENTS);

const OUTLOOK = {
  weeks: ["2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"],
  paid: [
    { expected: 0.9734, sd: 0.2412, parts: ["calendar", "China National Day holiday +2", "Steam Next Fest October -1"] },
    { expected: 0.97, sd: 0.21, parts: ["calendar", "Steam Next Fest October +0"] },
    { expected: 1.334, sd: 0.18, parts: ["calendar", "Steam Next Fest October +1"] },
    { expected: null, sd: null, parts: [] },
  ],
  free: [
    { expected: 1.5, sd: 0.6, parts: ["calendar"] },
    { expected: 1, sd: 0, parts: [] },
    { expected: 0.2, sd: 0.4, parts: [] },
    { expected: 1, sd: 0.1, parts: [] },
  ],
};

describe("what a week rests on", () => {
  test("in words, with the distance to each event", () => {
    expect(partText("calendar", KINDS, [])).toBe("the same week in past years");
    expect(partText("Steam Next Fest October -1", KINDS, [])).toBe("1 week before Next Fest October");
    expect(partText("Steam Next Fest October +0", KINDS, [])).toBe("the week of Next Fest October");
    expect(partText("US Thanksgiving to Cyber Monday +3", KINDS, [])).toBe("3 weeks after US Thanksgiving to Cyber Monday");
  });

  test("China's holidays only with Simplified Chinese, marked unconfirmed", () => {
    expect(partText("China National Day holiday +2", KINDS, ["english"])).toBeNull();
    expect(partText("China National Day holiday +2", KINDS, ["schinese"])).toBe(
      "2 weeks after China National Day holiday (unconfirmed)",
    );
  });
});

describe("the weeks", () => {
  const band = bandEvents(EVENTS, OUTLOOK.weeks[0], 4).events;
  const v = outlookView(OUTLOOK, "paid", { events: EVENTS, band, languages: ["english"] });

  test("value and spread with two decimals, and what each rests on", () => {
    const w = v.weeks[0];
    expect([w.value, w.spread, w.drivers]).toEqual([
      "0.97",
      "typical spread across years 0.73 to 1.21",
      "From the same week in past years; 1 week before Next Fest October.",
    ]);
    expect(w.label).toBe(
      "Week of 10/12 to 10/18: usually 0.97, typical spread across years 0.73 to 1.21. From the same week in past years; 1 week before Next Fest October.",
    );
    expect(w.detail).toBe("Week of 10/12 to 10/18: usually 0.97 (typical spread across years 0.73 to 1.21).");
  });

  test("a week without enough past years says so", () => {
    const w = v.weeks[3];
    expect([w.value, w.spread, w.drivers, w.bar]).toEqual(["n/a", null, null, null]);
    expect(w.label).toBe("Week of 11/2 to 11/8: not enough past years.");
  });

  test("events of the week, short and in full", () => {
    expect(v.weeks[1].events).toEqual(["Next Fest October"]);
    expect(v.weeks[1].eventsFull).toEqual(["Steam Next Fest October 2026"]);
  });

  test("month names where a month starts, this week marked", () => {
    expect(v.weeks.map((w) => w.month)).toEqual(["Oct", null, null, "Nov"]);
    expect(v.weeks.map((w) => w.day)).toEqual(["12", "19", "26", "2"]);
    expect(v.weeks.map((w) => w.current)).toEqual([true, false, false, false]);
  });

  test("bars sit around 1.0 on a scale that holds every spread", () => {
    expect(v.scale).toBe(0.55); // 1.334 + 0.18 is 0.514 above 1.0, rounded up to 0.05
    const [first, , third] = v.weeks;
    expect(first.bar.v).toBeCloseTo((0.9734 - 1) / 0.55, 10);
    expect(third.bar.hi).toBeCloseTo((1.514 - 1) / 0.55, 10);
  });

  test("the spread never goes under zero launches, and the scale has a floor", () => {
    const free = outlookView(OUTLOOK, "free", { events: EVENTS });
    expect(free.weeks[2].spread).toBe("typical spread across years 0.00 to 0.60");
    expect(free.scale).toBe(1.1);
    const flat = outlookView({ weeks: ["2026-10-12"], paid: [{ expected: 1, sd: 0.01, parts: [] }] }, "paid");
    expect(flat.scale).toBe(MIN_SCALE);
  });

  test("Chinese driver lists use Chinese punctuation", () => {
    const view = outlookView(OUTLOOK, "paid", { events: EVENTS, languages: ["schinese"] }, zh);
    expect(view.weeks[0].drivers).toContain("；");
    expect(view.weeks[0].drivers).not.toContain("; ");
    expect(view.weeks[0].label).not.toContain("。 ");
  });
});
