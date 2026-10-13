import { describe, expect, test } from "vitest";
import { countLine, formatNumber, summaryLine, tooFewPast } from "../src/count.js";
import { toDay, toIso } from "../src/lib/dates.js";
import { historyPanel, matchCount, MIN_GROUP } from "../src/lib/heatmap.js";
import { en } from "../src/strings.js";

const COUNTS = {
  paid: { upcoming: [1204, 20495], past: [3950, 82910] },
  free: { upcoming: [17, 1520], past: [5, 12232] },
};

describe("the phone summary", () => {
  const st = (tags, group = "paid") => ({ tags, group });

  test("reads tags, group and upcoming games of that group", () => {
    expect(summaryLine(st([1, 2, 3]), COUNTS)).toBe("3 tags · Paid · 1,204 upcoming");
    expect(summaryLine(st([7], "free"), COUNTS)).toBe("1 tag · Free · 17 upcoming");
    expect(summaryLine(st([]), COUNTS)).toBe("All tags · Paid · 1,204 upcoming");
  });

  test("has a label that says where tapping goes", () => {
    expect(en.bar.summaryLabel("1 tag · Free · 17 upcoming")).toBe("1 tag · Free · 17 upcoming. Back to the controls");
  });
});

describe("match count text", () => {
  test("reads as in the plan, with thousands separators and a middle dot", () => {
    expect(countLine(COUNTS, "paid").text).toBe("1,204 of 20,495 upcoming · 3,950 of 82,910 past launches");
    expect(countLine(COUNTS, "paid").text).not.toMatch(/—/);
  });

  test("is for the picked group", () => {
    const line = countLine(COUNTS, "free");
    expect(line.upcoming).toBe("17 of 1,520 upcoming");
    expect(line.past).toBe("5 of 12,232 past launches");
  });

  test("works on matchCount's own result", () => {
    const games = [
      { tags: [1], langs: ["english"], free: false },
      { tags: [2], langs: ["english"], free: false },
    ];
    const history = [{ tags: [1], langs: ["english"], free: false, launch_type: "full", launch_date: "2024-01-01" }];
    const counts = matchCount(games, history, { selection: [1], mode: "and", languages: ["english"] });
    expect(countLine(counts, "paid").text).toBe("1 of 2 upcoming · 1 of 1 past launches");
  });

  test("formats numbers for the locale", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
});

// Past launches of tag 1 in three weeks 14 weeks apart (so no week counts in
// another's baseline), with `sizes` launches each, after one launch of another
// tag that starts the data 13 weeks earlier. Busy is then size - 1 in each week,
// so the three weeks are exactly the quiet, normal and busy parts.
function past(sizes) {
  const start = toDay("2023-01-02"); // a Monday
  const rows = [{ tags: [2], langs: ["english"], free: false, launch_type: "full", launch_date: toIso(start), reviews_30d: 1 }];
  sizes.forEach((n, w) => {
    const day = toIso(start + 7 * (13 + 14 * w));
    for (let i = 0; i < n; i++) {
      rows.push({ tags: [1], langs: ["english"], free: false, launch_type: "full", launch_date: day, reviews_30d: i });
    }
  });
  return rows;
}

describe("too few past launches (red)", () => {
  const panel = (sizes) => historyPanel(past(sizes), { selection: [1], languages: ["english"] });

  test("uses the history panel's own threshold: every part needs MIN_GROUP launches", () => {
    expect(MIN_GROUP).toBe(30);
    expect(tooFewPast(panel([MIN_GROUP, MIN_GROUP + 1, MIN_GROUP + 2]), "paid")).toBe(false);
    expect(tooFewPast(panel([MIN_GROUP - 1, MIN_GROUP + 1, MIN_GROUP + 2]), "paid")).toBe(true);
  });

  test("is per group: no free launches at all is too few for free", () => {
    expect(tooFewPast(panel([MIN_GROUP, MIN_GROUP + 1, MIN_GROUP + 2]), "free")).toBe(true);
  });

  test("many launches can still be too few when the parts are uneven", () => {
    // 200 launches, but all in one week: one part, the other two empty
    expect(tooFewPast(panel([200]), "paid")).toBe(true);
  });
});
