import { describe, expect, test } from "vitest";
import { quarterly } from "../src/lib/trends.js";
import { en } from "../src/strings.js";
import { formatShare, niceTicks, trendView } from "../src/trendview.js";

const TODAY = "2026-10-13";
const past = (day, tags = [1], free = false) => ({
  launch_date: day,
  launch_type: "full",
  tags,
  langs: ["english"],
  free,
  reviews_30d: null,
});
// 2022: 1 of 4 paid launches a quarter with tag 1; from 2025 Q4 on, 3 of 4; 2026 Q4 so far: 1 of 2
const HISTORY = [];
for (let y = 2022; y <= 2026; y++) {
  for (const m of ["02", "05", "08", "11"]) {
    if (y === 2026 && m === "11") continue;
    const many = y === 2026 || (y === 2025 && m === "11");
    for (let i = 0; i < 4; i++) HISTORY.push(past(`${y}-${m}-0${i + 1}`, i < (many ? 3 : 1) ? [1] : [2]));
  }
}
HISTORY.push(past("2026-10-05"), past("2026-10-06", [2]), past("2024-08-09", [1], true));
const q = (selection = [1]) => quarterly(HISTORY, TODAY, { selection, languages: ["english"] });
const view = (v, opts = { tags: [1], languages: ["english"] }, sel = [1]) => trendView(q(sel), "paid", v, en, opts);

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
});

describe("the share view", () => {
  test("labels each quarter with its count, all launches and the share", () => {
    const v = view("share");
    expect(v.view).toBe("share");
    expect(v.bars).toHaveLength(20);
    expect(v.bars[10].label).toBe("2024 Q3: 1 of 4 paid launches (25.0%)");
    expect(v.bars[0].short).toBe("Q1");
    expect(v.ticks.map((t) => t.text)).toEqual(["0%", "20%", "40%", "60%", "80%"]);
    expect(v.bars[10].value).toBeCloseTo(0.25 / 0.8);
  });

  test("the quarter under way is partial, labelled so far with its days", () => {
    const v = view("share");
    expect(v.bars.at(-1)).toMatchObject({ partial: true, label: "2026 Q4 so far (Oct 1 to Oct 12): 1 of 2 paid launches (50.0%)" });
    expect(v.partial).toBe("Hatched: 2026 Q4 is not over (12 of 92 days so far).");
    expect(v.bars.filter((b) => b.partial)).toHaveLength(1);
  });

  test("says how 2022 compares with the last four full quarters", () => {
    expect(view("share").summary).toBe(
      "Your tags' share of paid launches in English: 25.0% in 2022, 75.0% in the last four full quarters.",
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
  test("the share would be 100% everywhere, so it shows the counts and says so", () => {
    const v = view("share", { tags: [], languages: ["english"] }, []);
    expect(v).toMatchObject({ view: "count", fallback: true });
    expect(v.bars[0].label).toBe("2022 Q1: 4 paid launches");
    expect(v.summary).toBe("All paid launches in English: 4 a quarter in 2022, 4 a quarter in the last four full quarters.");
  });
});

describe("the other views", () => {
  test("per quarter: counts from 0, whole steps", () => {
    const v = view("count");
    expect(v.ticks.map((t) => t.text)).toEqual(["0", "1", "2", "3"]);
    expect(v.bars[18].value).toBe(1);
    expect(v.summary).toBe(
      "Paid launches in English with your tags: 1 a quarter in 2022, 3 a quarter in the last four full quarters.",
    );
  });

  test("cumulative: launches since 2022", () => {
    const v = view("cumulative");
    expect(v.bars[1].label).toBe("2022 Q2: 2 paid launches since 2022 (1 that quarter)");
    // 15 quarters of 1, then 3 a quarter for four, then 1 so far: 28, on an axis up to 30
    expect(v.ticks.map((t) => t.text)).toEqual(["0", "10", "20", "30"]);
    expect(v.bars.at(-1).value).toBeCloseTo(28 / 30);
  });

  test("free games use their own counts", () => {
    const v = trendView(q(), "free", "count", en, { tags: [1], languages: [] });
    expect(v.bars[10].label).toBe("2024 Q3: 1 of 1 free launches (100.0%)");
    expect(v.bars[0].label).toBe("2022 Q1: no free launches");
    expect(v.summary).toBe(
      "Free launches in any language with your tags: 0 a quarter in 2022, 0 a quarter in the last four full quarters.",
    );
  });
});

test("an empty selection says so instead of a chart", () => {
  expect(view("share", { tags: [9], languages: ["english"] }, [9]).empty).toBe(en.trends.empty);
  expect(view("share").empty).toBeNull();
});
