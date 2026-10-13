import { describe, expect, test } from "vitest";
import { bandEvents } from "../src/events.js";
import {
  buildView,
  CUTS,
  formatCut,
  formatDate,
  formatUsual,
  formatValue,
  rawCuts,
  rowLabel,
  sometimeLines,
  step,
  weekHeads,
} from "../src/heatview.js";
import { heatmapRows } from "../src/lib/heatmap.js";
import { en } from "../src/strings.js";

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
// two launches of tag 1 (one with tag 2) in the last 52 weeks: a usual week of 2/52 and 1/52
const past = (tags, launch_date) => ({ tags, langs: ["english"], free: false, launch_type: "full", launch_date });
const HISTORY = [past([1, 2], "2026-03-02"), past([1], "2026-05-04"), past([3], "2026-06-01")];
const NAMES = new Map([
  [1, "Roguelike"],
  [2, "Shooter"],
]);
const rowsFor = (selection, mode = "and") =>
  heatmapRows(GAMES, TODAY, { selection, mode, languages: ["english"], history: HISTORY });

describe("shade steps", () => {
  test("count the cuts a value reaches; 1.0, a usual week, is where it turns dark", () => {
    expect(step(0, CUTS)).toBe(0);
    expect(step(0.09, CUTS)).toBe(0);
    expect(step(0.1, CUTS)).toBe(1);
    expect(step(0.99, CUTS)).toBe(3);
    expect(step(1, CUTS)).toBe(4);
    expect(step(2.9, CUTS)).toBe(6);
    expect(step(40, CUTS)).toBe(7);
  });

  test("raw counts use the same steps times the combination's usual week", () => {
    const rows = rowsFor([1, 2]);
    expect(rawCuts(rows, "paid")).toEqual(CUTS.map((c) => c / 52));
  });

  test("without a usual week, raw steps scale with half the biggest part", () => {
    const rows = rowsFor([2]);
    rows[0].typical = { paid: 0, free: 0 };
    expect(rawCuts(rows, "paid")).toEqual(CUTS.map((c) => c * 0.5));
  });
});

describe("numbers in cells", () => {
  test("zero is 0, small values keep one decimal, 10 and more are whole", () => {
    expect(formatValue(0)).toBe("0");
    expect(formatValue(0.03)).toBe("0.0");
    expect(formatValue(1.25)).toBe("1.3");
    expect(formatValue(9.94)).toBe("9.9");
    expect(formatValue(12.4)).toBe("12");
    expect(formatValue(1204)).toBe("1,204");
    expect(formatValue(3, en, true)).toBe("3");
  });

  test("legend steps show where they start", () => {
    expect([0, ...CUTS].map((c) => formatCut(c))).toEqual(["0", "0.1", "0.25", "0.5", "1.0", "1.5", "2.0", "3.0"]);
    expect(formatCut(0.65, en, true)).toBe("0.7");
    expect(formatCut(14.2, en, true)).toBe("14");
  });

  test("a usual week keeps two digits when it is under one game", () => {
    expect(formatUsual(431.29)).toBe("431");
    expect(formatUsual(7.23)).toBe("7.2");
    expect(formatUsual(0.385)).toBe("0.39");
  });

  test("dates read as the store's short dates", () => {
    expect(formatDate("2026-10-12")).toBe("Oct 12");
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
    26,
  ).events;
  const weeks = weekHeads(rowsFor([1])[0].weeks, events);

  test("say this week, the month where it changes, and fade after 4 weeks", () => {
    expect(weeks[0]).toMatchObject({ iso: "2026-10-12", date: "Oct 12", to: "Oct 18", day: "12", month: "Oct", current: true, far: false });
    expect(weeks[1].month).toBeNull();
    expect(weeks[3]).toMatchObject({ date: "Nov 2", month: "Nov" });
    expect(weeks.map((w) => w.far).indexOf(true)).toBe(5);
    expect(weeks.filter((w) => w.current)).toHaveLength(1);
  });

  test("carry the events in each week", () => {
    expect(weeks[1].events.map((e) => e.short)).toEqual(["Next Fest October"]);
    expect(weeks[2].events).toEqual([]);
  });
});

describe("the view", () => {
  test("normalized by default: each part over the row's usual week, as text and a step", () => {
    const view = buildView(rowsFor([1, 2]), { group: "paid", names: NAMES });
    expect(view.rows.map((r) => r.label)).toEqual(["Roguelike", "Shooter", "All of these"]);
    const combo = view.rows[2];
    expect(combo.usual).toBe("Usual week: 0.019"); // 1 launch in 52 weeks
    expect(view.rows[0].usual).toBe("Usual week: 0.038");
    // week 0: game 1 exact; a usual week is 1/52, so 52
    expect(combo.cells[0].parts.map((p) => [p.part, p.text, p.step])).toEqual([
      ["exact", "52", 7],
      ["spread", "0", 0],
    ]);
    expect(view.parts).toEqual(["exact", "spread"]);
    expect(combo.cells[0].label).toBe(
      "All of these, week of Oct 12: exact dates 52, month or quarter dates 0 (1.0 = a usual week)",
    );
  });

  test("raw counts: whole games for exact dates, decimals for spread ones", () => {
    const view = buildView(rowsFor([1, 2]), { group: "paid", raw: true, names: NAMES });
    const nov = view.rows[2].cells[3]; // week of Nov 2: 7 of the 30 November days
    expect(nov.parts.map((p) => p.text)).toEqual(["0", "0.2"]);
    expect(nov.label).toMatch(/month or quarter dates 0\.2 games$/);
    expect(view.rows[0].cells[0].parts[0].text).toBe("2"); // games 1 and 2
  });

  test("the year part only with the year layer, and far weeks say so", () => {
    const view = buildView(rowsFor([1]), { group: "paid", year: true, raw: true, names: NAMES });
    expect(view.parts).toEqual(["exact", "spread", "year"]);
    expect(view.rows[0].cells[20].parts[2].text).toBe("0.0"); // 1/52 of a 2027 game
    expect(view.rows[0].cells[20].label).toMatch(/year only 0\.0 games\. Dates still being set$/);
  });

  test("the picked group only", () => {
    const view = buildView(rowsFor([1]), { group: "free", raw: true, names: NAMES });
    expect(view.rows[0].cells[0].parts[0].text).toBe("1"); // game 7
    expect(view.rows[0].usual).toBe("No launches last year");
  });

  test("a row without a usual week shows counts unshaded in the normalized view", () => {
    const view = buildView(rowsFor([1]), { group: "free", names: NAMES });
    const part = view.rows[0].cells[0].parts[0];
    expect([part.text, part.step]).toEqual(["1", 0]);
    expect(view.rows[0].cells[0].label).toMatch(/exact dates 1, month or quarter dates 0 games$/);
  });

  test("events go into the cell's label", () => {
    const band = bandEvents(
      [{ name: "Steam Next Fest October 2026", type: "next_fest", start: "2026-10-19", end: "2026-10-26" }],
      "2026-10-12",
      26,
    ).events;
    const view = buildView(rowsFor([]), { group: "paid", band });
    expect(view.rows[0].label).toBe("All games");
    expect(view.rows[0].cells[1].label).toMatch(/\. Events: Steam Next Fest October 2026$/);
  });

  test("says when nothing matches, or only the combination is empty", () => {
    const none = heatmapRows(GAMES, TODAY, { selection: [9], languages: ["english"], history: HISTORY });
    expect(buildView(none, { group: "paid" }).empty).toBe(en.ahead.empty);
    const games = GAMES.filter((g) => g.appid !== 1 && g.appid !== 4);
    const rows = heatmapRows(games, TODAY, { selection: [1, 2], languages: ["english"], history: HISTORY });
    expect(buildView(rows, { group: "paid", names: NAMES }).empty).toBe(en.ahead.emptyCombo);
    expect(buildView(rowsFor([1, 2]), { group: "paid", names: NAMES }).empty).toBeNull();
  });
});

describe("the sometime line", () => {
  test("one per year, then later, for the group", () => {
    const rows = rowsFor([1]);
    expect(sometimeLines(rows[0], "paid")).toEqual(["Sometime in 2027: 1 game", "Later: 1 game"]);
    expect(sometimeLines(rows[0], "free")).toEqual([en.ahead.noSometime]);
  });

  test("counts with thousands separators", () => {
    const row = { sometime: { 2027: { paid: { games: 2631 } } } };
    expect(sometimeLines(row, "paid")).toEqual(["Sometime in 2027: 2,631 games"]);
  });
});
