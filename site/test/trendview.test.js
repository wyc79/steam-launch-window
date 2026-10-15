import { describe, expect, test } from "vitest";
import { quarterly } from "../src/lib/trends.js";
import { en } from "../src/strings.js";
import { formatShare, niceTicks, tickTexts, trendView, viewsFor } from "../src/trendview.js";

const TODAY = "2026-10-13";
const past = (day, tags = [1], free = false) => ({
  launch_date: day,
  launch_type: "full",
  tags,
  langs: ["english"],
  free,
  reviews_30d: null,
  listed: true,
});
// `niche(i)` launches with tag 1 and `rest(i)` with tag 2 in quarter i (0 is 2022 Q1,
// 19 is 2026 Q4, under way on TODAY: its launches fall on Oct 5)
function history(niche, rest, free = false) {
  const out = [];
  for (let i = 0; i < 20; i++) {
    const [y, m] = [2022 + Math.floor(i / 4), ["02", "05", "08", "10"][i % 4]];
    const day = (j) => (i === 19 ? `${y}-${m}-05` : `${y}-${i % 4 === 3 ? "11" : m}-${String(1 + (j % 28)).padStart(2, "0")}`);
    for (let j = 0; j < niche(i); j++) out.push(past(day(j), [1], free));
    for (let j = 0; j < rest(i); j++) out.push(past(day(j), [2], free));
  }
  return out;
}
// 10 of 40 paid launches a quarter with tag 1 to 2025 Q3, then 30 of 40; 2026 Q4 so far: 1 of 2
const HISTORY = [
  ...history(
    (i) => (i === 19 ? 1 : i >= 15 ? 30 : 10),
    (i) => (i === 19 ? 1 : i >= 15 ? 10 : 30),
  ),
  past("2024-08-09", [1], true),
];
const q = (h = HISTORY, today = TODAY) => quarterly(h, today, { selection: [1], languages: ["english"] });
const opts = { tags: [1], languages: ["english"] };
const view = (v, o = opts, data = q()) => trendView(data, "paid", v, en, o);

describe("formatting", () => {
  test("shares: one decimal, two significant digits under 1%", () => {
    expect([0.056, 0.0004, 0.0056, 0, 1].map((x) => formatShare(x))).toEqual(["5.6%", "0.04%", "0.56%", "0.0%", "100.0%"]);
  });

  test("the axis goes up in round steps from 0 to at least the largest value", () => {
    expect(niceTicks(412, true)).toEqual([0, 200, 400, 600]);
    expect(niceTicks(0.061, false)).toEqual([0, 0.02, 0.04, 0.06, 0.08]);
    expect(niceTicks(3, true)).toEqual([0, 1, 2, 3]);
    expect(niceTicks(0.75, false)).toEqual([0, 0.2, 0.4, 0.6, 0.8]);
    expect(niceTicks(0, true)).toEqual([0, 1]);
    expect(niceTicks(0, false)).toEqual([0, 0.01]);
  });

  test("tick labels take the decimals their step needs, so none repeat", () => {
    expect(tickTexts(niceTicks(0.0003, false), false)).toEqual(["0%", "0.01%", "0.02%", "0.03%"]);
    expect(tickTexts(niceTicks(0.0009, false), false)).toEqual(["0%", "0.025%", "0.05%", "0.075%", "0.1%"]);
    expect(tickTexts(niceTicks(0.061, false), false)).toEqual(["0%", "2%", "4%", "6%", "8%"]);
    expect(tickTexts([0, 2000, 4000], true)).toEqual(["0", "2,000", "4,000"]);
  });
});

describe("the share view", () => {
  test("labels each quarter with its count, all launches and the share", () => {
    const v = view("share");
    expect(v.view).toBe("share");
    expect(v.bars).toHaveLength(20);
    expect(v.bars[10].label).toBe("2024 Q3: 10 of 40 paid launches (25.0%)");
    expect(v.bars[0].short).toBe("Q1");
    expect(v.ticks.map((t) => t.text)).toEqual(["0%", "20%", "40%", "60%", "80%"]);
    expect(v.bars[10].value).toBeCloseTo(0.25 / 0.8);
  });

  test("the quarter under way is partial, labelled so far with its days", () => {
    const v = view("share");
    expect(v.bars.at(-1)).toMatchObject({
      partial: true,
      over: false,
      label: "2026 Q4 so far (10/1 to 10/12; recent, tags may still change): 1 of 2 paid launches (50.0%)",
    });
    expect(v.partial).toBe("Hatched: recent quarters, whose tags may still change. 2026 Q4 so far: 12 of 92 days.");
    expect(v.bars.filter((b) => b.partial)).toHaveLength(1);
  });

  test("on its first day the quarter under way says so, without 0 days", () => {
    const v = view("share", opts, q(HISTORY, "2026-10-01"));
    expect(v.partial).toBe("Hatched: recent quarters, whose tags may still change. 2026 Q4 has just started.");
    expect(v.bars.at(-1).label).toBe("2026 Q4 (just started): no paid launches");
  });

  test("the scale comes from the full quarters; a quarter under way above it is cut and says so", () => {
    const more = [...HISTORY, ...Array.from({ length: 6 }, () => past("2026-10-06"))]; // 7 of 8 so far
    const v = view("share", opts, q(more));
    expect(v.ticks.at(-1).text).toBe("80%");
    expect(v.bars.at(-1)).toMatchObject({ over: true, value: 1 });
    expect(v.bars.at(-1).label).toMatch(/: 7 of 8 paid launches \(87\.5%\), above the scale$/);
    expect(v.bars.filter((b) => b.over)).toHaveLength(1);
  });

  test("the partial quarter and the two full ones before it are recent, and say so", () => {
    const v = view("share");
    expect(v.recent).toEqual({ from: 17, span: 3 });
    expect(v.bars.map((b) => b.recent).lastIndexOf(false)).toBe(16);
    expect(v.bars[17].label).toBe("2026 Q2 (recent, tags may still change): 30 of 40 paid launches (75.0%)");
    expect(v.bars[16].label).toBe("2026 Q1: 30 of 40 paid launches (75.0%)");
  });

  test("compares 2022 with the four full quarters before the recent ones, with the launches behind each", () => {
    expect(view("share").summary).toBe(
      "Your tags' share of paid launches in English: 25.0% in 2022 (40 launches), 50.0% in 2025 Q2 to 2026 Q1 (80).",
    );
  });

  test("groups the quarters by year", () => {
    expect(view("share").years.map((y) => [y.year, y.from, y.span])).toEqual([
      [2022, 0, 4],
      [2023, 4, 4],
      [2024, 8, 4],
      [2025, 12, 4],
      [2026, 16, 4],
    ]);
  });
});

describe("with no tags", () => {
  test("there is no share to pick, so the counts show", () => {
    expect(viewsFor([])).toEqual(["count", "cumulative"]);
    expect(viewsFor([1])).toEqual(["share", "count", "cumulative"]);
    const v = view("share", { tags: [], languages: ["english"] }, quarterly(HISTORY, TODAY, { languages: ["english"] }));
    expect(v.view).toBe("count");
    expect(v.bars[0].label).toBe("2022 Q1: 40 paid launches");
    expect(v.summary).toBe("All paid launches in English: 40 a quarter in 2022, 40 a quarter in 2025 Q2 to 2026 Q1.");
  });
});

describe("the other views", () => {
  test("per quarter: counts from 0, whole steps", () => {
    const v = view("count");
    expect(v.ticks.map((t) => t.text)).toEqual(["0", "10", "20", "30"]);
    expect(v.bars[18].value).toBe(1);
    expect(v.summary).toBe(
      "Paid launches in English with your tags: 10 a quarter in 2022, 20 a quarter in 2025 Q2 to 2026 Q1.",
    );
  });

  test("per quarter: averages under 10 keep one decimal", () => {
    const small = history(
      (i) => [5, 5, 6, 6][i] ?? (i >= 13 && i <= 16 ? [7, 7, 8, 7][i - 13] : 5),
      () => 20,
    );
    expect(view("count", opts, q(small)).summary).toBe(
      "Paid launches in English with your tags: 5.5 a quarter in 2022, 7.3 a quarter in 2025 Q2 to 2026 Q1.",
    );
  });

  test("cumulative: launches since 2022, the quarter under way on the scale", () => {
    const v = view("cumulative");
    expect(v.bars[1].label).toBe("2022 Q2: 20 paid launches since 2022 (10 that quarter)");
    // 15 quarters of 10, then 30 a quarter for four, then 1 so far: 271, on an axis up to 300
    expect(v.ticks.map((t) => t.text)).toEqual(["0", "100", "200", "300"]);
    expect(v.bars.at(-1)).toMatchObject({ over: false });
    expect(v.bars.at(-1).value).toBeCloseTo(271 / 300);
  });

  test("too few launches in a window: no comparison, and never n/a", () => {
    const v = trendView(q(), "free", "share", en, { tags: [1], languages: [] });
    expect(v.bars[10].label).toBe("2024 Q3: 1 of 1 free launches (100.0%)");
    expect(v.bars[0].label).toBe("2022 Q1: no free launches");
    expect(v.summary).toBe("Too few launches to compare 2022 with recent years (each needs 20).");
    expect(v.few).toBe(true);
    expect(view("share").few).toBe(false);
    expect(trendView(q(), "free", "count", en, { tags: [1], languages: [] }).summary).toBe(v.summary);
  });
});

test("an empty selection says so instead of a chart", () => {
  expect(trendView(quarterly(HISTORY, TODAY, { selection: [9] }), "paid", "share", en, { tags: [9] }).empty).toBe(
    en.trends.empty,
  );
  expect(view("share").empty).toBeNull();
});
