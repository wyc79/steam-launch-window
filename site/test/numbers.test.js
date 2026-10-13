import { describe, expect, test } from "vitest";
import { heatmapRows, matchCount, nicheTrend, weekGames } from "../src/lib/heatmap.js";
import { outlook } from "../src/lib/season.js";
import { createNumbers, heatmapKey, numbersKey, tagCounts } from "../src/numbers.js";
import { DEFAULT } from "../src/state.js";

const game = (tags, langs, free = false) => ({ tags, langs, free });
const GAMES = [
  game([1, 2], ["english"]),
  game([1], ["english", "schinese"]),
  game([2], ["schinese"]),
  game([1, 3], ["english"], true),
];
const HISTORY = GAMES.map((g, i) => ({ ...g, launch_type: "full", launch_date: `2024-0${i + 1}-01`, reviews_30d: i }));
const pick = (patch) => ({ ...DEFAULT, ...patch });

describe("shared numbers", () => {
  test("are matchCount and historyPanel for the selection", () => {
    const numbers = createNumbers(GAMES, HISTORY);
    const { counts, panel } = numbers.get(pick({ tags: [1] }));
    expect(counts).toEqual(matchCount(GAMES, HISTORY, { selection: [1], mode: "and", languages: ["english"] }));
    expect(panel.measure).toBe("relative");
    expect(Object.keys(panel)).toEqual(expect.arrayContaining(["paid", "free", "matched", "total"]));
  });

  test("switching paid / free reuses the same result", () => {
    const numbers = createNumbers(GAMES, HISTORY);
    const paid = numbers.get(pick({ tags: [1] }));
    expect(numbers.has(pick({ tags: [1], group: "free" }))).toBe(true);
    expect(numbers.get(pick({ tags: [1], group: "free" }))).toBe(paid);
  });

  test("the order tags and languages were picked in does not matter", () => {
    expect(numbersKey(pick({ tags: [2, 1], languages: ["schinese", "english"] }))).toBe(
      numbersKey(pick({ tags: [1, 2], languages: ["english", "schinese"] })),
    );
  });

  test("tags, mode, languages and the measure each give a new result", () => {
    const numbers = createNumbers(GAMES, HISTORY);
    const base = numbers.get(pick({ tags: [1] }));
    for (const patch of [{ tags: [2] }, { mode: "or" }, { languages: [] }, { measure: "raw" }]) {
      expect(numbers.has(pick({ tags: [1], ...patch }))).toBe(false);
      expect(numbers.get(pick({ tags: [1], ...patch }))).not.toBe(base);
    }
    expect(numbers.get(pick({ tags: [1], measure: "raw" })).panel.measure).toBe("raw");
  });

  test("keeps the recent selections, not all of them", () => {
    const numbers = createNumbers(GAMES, HISTORY);
    numbers.get(pick({ tags: [0] }));
    for (let t = 1; t <= 20; t++) numbers.get(pick({ tags: [t] }));
    expect(numbers.has(pick({ tags: [0] }))).toBe(false);
    expect(numbers.has(pick({ tags: [20] }))).toBe(true);
  });
});

describe("tag counts for the tag list", () => {
  test("count upcoming games per tag for the languages and the group", () => {
    expect(tagCounts(GAMES, { languages: ["english"], group: "paid" })).toEqual(
      new Map([
        [1, 2],
        [2, 1],
      ]),
    );
    expect(tagCounts(GAMES, { languages: ["schinese"], group: "paid" })).toEqual(
      new Map([
        [1, 1],
        [2, 1],
      ]),
    );
    expect(tagCounts(GAMES, { languages: [], group: "free" })).toEqual(
      new Map([
        [1, 1],
        [3, 1],
      ]),
    );
  });

  test("are cached per languages and group; picking tags does not recount", () => {
    const numbers = createNumbers(GAMES, HISTORY);
    const first = numbers.tagCounts(pick({}));
    expect(numbers.tagCounts(pick({ tags: [1, 2], mode: "or" }))).toBe(first);
    expect(numbers.tagCounts(pick({ group: "free" }))).not.toBe(first);
    expect(numbers.tagCounts(pick({ languages: ["schinese"] }))).not.toBe(first);
  });
});

describe("the heatmap's numbers", () => {
  const TODAY = "2026-10-13";
  const dated = (appid, tags, free = false) => ({
    appid,
    name: `G${appid}`,
    tags,
    langs: ["english"],
    free,
    precision: "day",
    date: "2026-10-14",
    date_end: "2026-10-14",
  });
  const UP = [dated(1, [1, 2]), dated(2, [1]), dated(3, [1], true)];
  const numbers = () => createNumbers(UP, HISTORY, TODAY);

  test("are heatmapRows for the selection, with the typical week", () => {
    const rows = numbers().heatmap(pick({ tags: [1, 2] }));
    expect(rows).toEqual(heatmapRows(UP, TODAY, { selection: [1, 2], mode: "and", languages: ["english"], history: HISTORY }));
    expect(rows.map((r) => r.tags)).toEqual([[1], [2], [1, 2]]);
    expect(rows[0].typical).not.toBeNull();
  });

  test("are computed once: paid / free and the panel's measure reuse them", () => {
    const shared = numbers();
    const st = pick({ tags: [1] });
    expect(shared.hasHeatmap(st)).toBe(false);
    const rows = shared.heatmap(st);
    for (const patch of [{ group: "free" }, { measure: "raw" }, { languages: ["english"] }]) {
      expect(shared.hasHeatmap({ ...st, ...patch })).toBe(true);
      expect(shared.heatmap({ ...st, ...patch })).toBe(rows);
    }
  });

  test("a tag's own row is reused when more tags are picked", () => {
    const shared = numbers();
    const one = shared.heatmap(pick({ tags: [1] }));
    const two = shared.heatmap(pick({ tags: [1, 2], mode: "or" }));
    expect(two[0]).toBe(one[0]);
    expect(two[2]).toEqual(heatmapRows(UP, TODAY, { selection: [1, 2], mode: "or", languages: ["english"], history: HISTORY })[2]);
  });

  test("keep the order tags were picked in (it is the order of the rows), not that of languages", () => {
    expect(heatmapKey(pick({ tags: [2, 1] }))).not.toBe(heatmapKey(pick({ tags: [1, 2] })));
    expect(heatmapKey(pick({ languages: ["schinese", "english"] }))).toBe(
      heatmapKey(pick({ languages: ["english", "schinese"] })),
    );
    expect(numbers().heatmap(pick({ tags: [2, 1] })).map((r) => r.tags)).toEqual([[2], [1], [2, 1]]);
  });

  test("tags, mode and languages each give a new result; old ones drop out", () => {
    const shared = numbers();
    const base = shared.heatmap(pick({ tags: [1] }));
    for (const patch of [{ tags: [2] }, { mode: "or" }, { languages: [] }]) {
      expect(shared.heatmap(pick({ tags: [1], ...patch }))).not.toBe(base);
    }
    for (let t = 3; t < 25; t++) shared.heatmap(pick({ tags: [t] }));
    expect(shared.hasHeatmap(pick({ tags: [1] }))).toBe(false);
  });

  test("the trend line's numbers are nicheTrend for each row, none for all games", () => {
    const shared = numbers();
    const st = pick({ tags: [1, 2], mode: "or" });
    const trends = shared.trend(st);
    const q = { mode: "or", languages: ["english"] };
    expect(trends).toEqual([
      nicheTrend(UP, HISTORY, TODAY, { ...q, selection: [1] }),
      nicheTrend(UP, HISTORY, TODAY, { ...q, selection: [2] }),
      nicheTrend(UP, HISTORY, TODAY, { ...q, selection: [1, 2] }),
    ]);
    expect(shared.trend({ ...st, group: "free" })).toBe(trends);
    expect(shared.trend(pick({}))).toEqual([null]);
  });

  test("a week's games are weekGames' list for the picked group, in its order", () => {
    const shared = numbers();
    const paid = shared.weekGames(pick({}), [1], "2026-10-12", false);
    const all = weekGames(UP, TODAY, "2026-10-12", { selection: [1], mode: "and", languages: ["english"] });
    expect(paid.map((g) => g.appid)).toEqual(all.filter((g) => !g.free).map((g) => g.appid));
    expect(shared.weekGames(pick({ group: "free" }), [1], "2026-10-12", false).map((g) => g.appid)).toEqual([3]);
    expect(shared.game(2).name).toBe("G2");
  });
});

describe("the outlook", () => {
  const EVENTS = [{ name: "Steam Next Fest October 2024", type: "next_fest", start: "2024-10-14" }];

  test("is season.outlook for 26 weeks from the snapshot, for the languages", () => {
    const shared = createNumbers([], HISTORY, "2026-10-13");
    const st = pick({ languages: ["schinese"] });
    expect(shared.outlook(st, EVENTS)).toEqual(outlook(HISTORY, EVENTS, "2026-10-13", { weeks: 26, languages: ["schinese"] }));
  });

  test("is cached per languages: tags, mode, group and measure reuse it", () => {
    const shared = createNumbers([], HISTORY, "2026-10-13");
    const first = shared.outlook(pick({}), EVENTS);
    for (const patch of [{ tags: [1] }, { mode: "or" }, { group: "free" }, { measure: "raw" }]) {
      expect(shared.hasOutlook(pick(patch), EVENTS)).toBe(true);
      expect(shared.outlook(pick(patch), EVENTS)).toBe(first);
    }
    expect(shared.hasOutlook(pick({ languages: [] }), EVENTS)).toBe(false);
    expect(shared.hasOutlook(pick({}), [])).toBe(false); // other events: computed again
  });
});
