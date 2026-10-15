import { describe, expect, test } from "vitest";
import { bandEvents } from "../src/events.js";
import {
  buildView,
  countsText,
  countText,
  CUTS,
  formatCut,
  formatDate,
  formatRatio,
  formatValue,
  rowLabel,
  shownValue,
  sometimeLines,
  spokenValue,
  step,
  trendLines,
  weekHeads,
} from "../src/heatview.js";
import { heatmapRows, WEEKS } from "../src/lib/heatmap.js";
import { en, zh } from "../src/strings.js";

const TODAY = "2026-10-13"; // a Tuesday: the first week starts Monday 2026-10-12
const up = (appid, tags, precision, date, date_end, extra = {}) => ({
  appid,
  name: `Game ${appid}`,
  tags,
  langs: ["english"],
  free: false,
  precision,
  date,
  date_end,
  followers: null,
  hype_src: null,
  moved: null,
  ...extra,
});
const GAMES = [
  up(1, [1, 2], "day", "2026-10-14", "2026-10-14"),
  up(2, [1], "day", "2026-10-15", "2026-10-15"),
  up(3, [2], "day", "2026-10-21", "2026-10-21"),
  up(4, [1, 2], "month", "2026-11-01", "2026-11-30"),
  up(5, [1], "year", "2027-01-01", "2027-12-31"),
  up(6, [1], "year", "2099-01-01", "2099-12-31"),
  up(7, [1], "day", "2026-10-14", "2026-10-14", { free: true }),
];
const past = (tags, launch_date, free = false) => ({ tags, langs: ["english"], free, launch_type: "full", launch_date });
// tag 1: 104 paid launches in the last 52 weeks (a typical week of 2), 26 of them
// with tag 2 too (0.5 a week: too few, so counts); one free launch
const HISTORY = [
  ...Array.from({ length: 104 }, (_, i) => past(i % 4 ? [1] : [1, 2], weekDay(i % 52))),
  past([1], "2026-06-01", true),
];
function weekDay(k) {
  return new Date(Date.UTC(2025, 9, 20) + k * 7 * 86400000).toISOString().slice(0, 10);
}
const NAMES = new Map([
  [1, "Roguelike"],
  [2, "Shooter"],
]);
const rowsFor = (selection, mode = "and") =>
  heatmapRows(GAMES, TODAY, { selection, mode, languages: ["english"], history: HISTORY });

describe("shade steps", () => {
  test("count the cuts a value reaches; 1.0, a typical week, is where it turns dark", () => {
    expect(step(0)).toBe(0);
    expect(step(0.09)).toBe(0);
    expect(step(0.1)).toBe(1);
    expect(step(0.99)).toBe(3);
    expect(step(1)).toBe(4);
    expect(step(2.9)).toBe(6);
    expect(step(40)).toBe(7);
  });

  test("follow the number as shown: 0.96 shows 1.0 and is shaded as 1.0", () => {
    expect(shownValue(0.96)).toBe(1);
    expect(step(shownValue(0.96))).toBe(4);
    expect(shownValue(0.94)).toBe(0.9);
    expect(shownValue(9.96)).toBe(10);
    expect(shownValue(2.4, true)).toBe(2);
  });
});

describe("numbers in cells", () => {
  test("zero is 0, a little is <0.1, one decimal below 10, whole from there", () => {
    expect(formatValue(0)).toBe("0");
    expect(formatValue(0.03)).toBe("<0.1");
    expect(formatValue(0.05)).toBe("0.1");
    expect(formatValue(1.25)).toBe("1.3");
    expect(formatValue(9.94)).toBe("9.9");
    expect(formatValue(9.96)).toBe("10"); // not "10.0"
    expect(formatValue(12.4)).toBe("12");
    expect(formatValue(1204)).toBe("1,204");
    expect(formatValue(3, en, true)).toBe("3");
  });

  test("read aloud, a little is under 0.1", () => {
    expect(spokenValue(0.03)).toBe("under 0.1");
    expect(spokenValue(0)).toBe("0");
    expect(spokenValue(1.2)).toBe("1.2");
  });

  test("legend steps show where they start", () => {
    expect([0, ...CUTS].map((c) => formatCut(c))).toEqual(["0", "0.1", "0.25", "0.5", "1.0", "1.5", "2.0", "3.0"]);
  });

  test("dates read as the store's short dates", () => {
    expect(formatDate("2026-10-12")).toBe("10/12");
  });
});

test("row labels: all games, a tag's name, or the combination", () => {
  expect(rowLabel([], "and", NAMES)).toBe("All games");
  expect(rowLabel([2], "and", NAMES)).toBe("Shooter");
  expect(rowLabel([1, 2], "and", NAMES)).toBe("All of these");
  expect(rowLabel([1, 2], "or", NAMES)).toBe("Any of these");
});

describe("week heads", () => {
  const events = bandEvents(
    [{ name: "Steam Next Fest October 2026", type: "next_fest", start: "2026-10-19", end: "2026-10-26" }],
    "2026-10-12",
    WEEKS,
  ).events;
  const weeks = weekHeads(rowsFor([1])[0].weeks, events);

  test("13 weeks: dates, this week, and faded after 4 weeks", () => {
    expect(weeks).toHaveLength(13);
    expect(weeks[0]).toMatchObject({ iso: "2026-10-12", date: "10/12", to: "10/18", current: true, far: false });
    expect(weeks[3].date).toBe("11/2");
    expect(weeks.map((w) => w.far).indexOf(true)).toBe(5);
    expect(weeks.filter((w) => w.current)).toHaveLength(1);
  });

  test("carry the events in each week", () => {
    expect(weeks[1].events.map((e) => e.name)).toEqual(["Steam Next Fest October 2026"]);
    expect(weeks[2].events).toEqual([]);
  });
});

describe("the view", () => {
  test("normalized by default: each part over the row's typical week, as text and a step", () => {
    const view = buildView(rowsFor([1]), { group: "paid", names: NAMES });
    const row = view.rows[0];
    expect(row.note).toBe("about 2.0 launches in a typical week");
    expect(row.counts).toBe(false);
    // week 0: games 1 and 2 exact, a typical week of 2
    expect(row.cells[0].parts.map((p) => [p.part, p.text, p.step])).toEqual([
      ["exact", "1.0", 4],
      ["spread", "0", 0],
    ]);
    expect(view.parts).toEqual(["exact", "spread"]);
    expect(row.cells[0].label).toBe(
      "Roguelike, week of 10/12: exact dates 1.0, month or quarter dates 0 (1.0 = as many as a typical week). Week of 10/12: 2 with exact dates, 0 games' worth from month or quarter dates, 2 in a typical week.",
    );
  });

  test("raw counts change the numbers, not the shades", () => {
    const normal = buildView(rowsFor([1]), { group: "paid", names: NAMES }).rows[0];
    const raw = buildView(rowsFor([1]), { group: "paid", raw: true, names: NAMES }).rows[0];
    expect(raw.cells[0].parts[0].text).toBe("2"); // games 1 and 2
    expect(raw.cells.map((c) => c.parts.map((p) => p.step))).toEqual(normal.cells.map((c) => c.parts.map((p) => p.step)));
    expect(raw.cells[3].label).toMatch(/month or quarter dates 0\.2 games. Week of /); // 7 of the 30 November days
  });

  test("a row with under one launch in a typical week shows counts, unshaded, and says so", () => {
    const view = buildView(rowsFor([1, 2]), { group: "paid", names: NAMES });
    const combo = view.rows[2];
    expect(combo.counts).toBe(true);
    expect(combo.note).toBe("counts: only 26 launches in the last year");
    expect(combo.cells[0].parts.map((p) => [p.text, p.step])).toEqual([
      ["1", 0],
      ["0", 0],
    ]);
    expect(combo.cells[0].label).toMatch(/exact dates 1, month or quarter dates 0 games. Week of /);
    expect(view.anyCounts).toBe(true);
    expect(buildView(rowsFor([1]), { group: "paid", names: NAMES }).anyCounts).toBe(false);
  });

  test("no past launches at all: counts too", () => {
    const view = buildView(rowsFor([2]), { group: "free", raw: true, names: NAMES });
    expect(view.rows[0].note).toBe("counts: no launches in the last year");
    const one = buildView(rowsFor([1]), { group: "free", names: NAMES }).rows[0];
    expect(one.note).toBe("counts: only 1 launch in the last year");
    expect(one.cells[0].parts[0].text).toBe("1"); // game 7
  });

  test("the year part only with the year layer, and far weeks say so", () => {
    const view = buildView(rowsFor([1]), { group: "paid", year: true, raw: true, names: NAMES });
    expect(view.parts).toEqual(["exact", "spread", "year"]);
    expect(view.rows[0].cells[12].parts[2].text).toBe("<0.1"); // 1/52 of a 2027 game in Jan 4 to 10 (6/365)
    expect(view.rows[0].cells[12].label).toMatch(/year only under 0\.1 games\. Dates still being set. Week of /);
  });

  test("events go into the cell's label", () => {
    const band = bandEvents(
      [{ name: "Steam Next Fest October 2026", type: "next_fest", start: "2026-10-19", end: "2026-10-26" }],
      "2026-10-12",
      WEEKS,
    ).events;
    const view = buildView(rowsFor([]), { group: "paid", band });
    expect(view.rows[0].label).toBe("All games");
    expect(view.rows[0].cells[1].label).toMatch(/\. Events: Steam Next Fest October 2026. Week of /);
  });

  test("Chinese cell labels use Chinese punctuation", () => {
    const label = buildView(rowsFor([1]), { group: "paid", names: NAMES, s: zh }).rows[0].cells[0].label;
    expect(label).toContain("确定日期");
    expect(label).toContain("。");
    expect(label).not.toContain(". ");
  });

  test("says when nothing matches, or only the combination is empty", () => {
    const none = heatmapRows(GAMES, TODAY, { selection: [9], languages: ["english"], history: HISTORY });
    expect(buildView(none, { group: "paid" }).empty).toBe(en.ahead.empty);
    const games = GAMES.filter((g) => g.appid !== 1 && g.appid !== 4);
    const rows = heatmapRows(games, TODAY, { selection: [1, 2], languages: ["english"], history: HISTORY });
    expect(buildView(rows, { group: "paid", names: NAMES }).empty).toBe(en.ahead.emptyCombo);
    expect(en.ahead.emptyCombo).not.toMatch(/above/);
    expect(buildView(rowsFor([1, 2]), { group: "paid", names: NAMES }).empty).toBeNull();
  });

  test("the sometime line names the row it counts", () => {
    expect(buildView(rowsFor([1, 2]), { group: "paid", names: NAMES }).sometime.row).toBe("All of these");
    expect(buildView(rowsFor([1]), { group: "paid", names: NAMES }).sometime).toEqual({
      row: "Roguelike",
      lines: ["sometime in 2027: 1 game", "later: 1 game"],
    });
  });
});

describe("the sometime lines", () => {
  test("one per year, then later, for the group", () => {
    const rows = rowsFor([1]);
    expect(sometimeLines(rows[0], "paid")).toEqual(["sometime in 2027: 1 game", "later: 1 game"]);
    expect(sometimeLines(rows[0], "free")).toEqual([en.ahead.noSometime]);
  });

  test("count with thousands separators", () => {
    const row = { sometime: { 2027: { paid: { games: 2631 } } } };
    expect(sometimeLines(row, "paid")).toEqual(["sometime in 2027: 2,631 games"]);
  });
});

test("the section's intro says how many weeks it shows", () => {
  expect(en.sections.ahead.intro).toContain(`${WEEKS} weeks`);
});

describe("the niche trend line", () => {
  const t = (ratio, clear) => ({ ratio, clear });
  const rows = [{ label: "Cozy" }, { label: "Card Game" }, { label: "Platformer" }, { label: "All of these" }];

  test("names each row whose share differs clearly for the picked group", () => {
    const trends = [
      { paid: t(2.0137, true), free: t(1.1, false) },
      { paid: t(1.3, false), free: t(3, true) },
      { paid: t(0.6912, true), free: t(1, false) },
      null,
    ];
    expect(trendLines(rows, trends, "paid")).toEqual([
      "Cozy is 2.0x as large a share of upcoming games (exact dates) as of last year's launches.",
      "Platformer is 0.69x as large a share of upcoming games (exact dates) as of last year's launches.",
    ]);
    expect(trendLines(rows, trends, "free")).toEqual([
      "Card Game is 3.0x as large a share of upcoming games (exact dates) as of last year's launches.",
    ]);
  });

  test("says nothing for all games or when nothing is clear", () => {
    expect(trendLines([{ label: "All games" }], [null], "paid")).toEqual([]);
    expect(trendLines(rows.slice(0, 1), [{ paid: t(null, false), free: t(null, false) }], "paid")).toEqual([]);
  });

  test("ratios to two significant digits", () => {
    expect([2, 1.25, 0.6912, 12.4].map((r) => formatRatio(r))).toEqual(["2.0", "1.3", "0.69", "12"]);
  });
});

describe("a cell's raw numbers (the tooltip)", () => {
  test("whole games as they are, spread shares as about", () => {
    expect([298, 113.6, 0.44, 0, 9.96].map((x) => countText(x))).toEqual(["298", "about 114", "about 0.4", "0", "about 10"]);
  });

  test("exact, the spread's worth and the typical week, from the cell's own values", () => {
    const cell = { exact: 274, spread: 240.3, year: 3.25 };
    expect(countsText(cell, 343.4, "10/19")).toBe(
      "Week of 10/19: 274 with exact dates, about 240 games' worth from month or quarter dates, about 343 in a typical week.",
    );
    expect(countsText(cell, 0.5, "10/19", true)).toBe(
      "Week of 10/19: 274 with exact dates, about 240 games' worth from month or quarter dates, about 3.3 from year-only dates, about 0.5 in a typical week.",
    );
  });
});
