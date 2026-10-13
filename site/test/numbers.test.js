import { describe, expect, test } from "vitest";
import { matchCount } from "../src/lib/heatmap.js";
import { createNumbers, numbersKey, tagCounts } from "../src/numbers.js";
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
