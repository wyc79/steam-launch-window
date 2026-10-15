import { describe, expect, test } from "vitest";
import { zh } from "../src/strings.js";
import { searchTags, SHOWN, tagName, tagNames } from "../src/tags.js";

// meta.json rows: [id, name, upcoming games, past launches, Simplified Chinese name]
const TAGS = [
  [19, "Action", 7857, 31736],
  [1663, "FPS", 900, 4000],
  [1774, "Shooter", 1650, 6607],
  [3959, "Roguelite", 1300, 5200],
  [1716, "Roguelike", 900, 4500],
  [42804, "Action Roguelike", 1100, 4800],
  [4182, "Singleplayer", 9000, 40000],
  [7368, "Local Multiplayer", 500, 3000],
  [3859, "Multiplayer", 2500, 11000],
  [1695, "Open World", 1200, 5000],
  [99999, null, 3, 3],
];
const names = (rows) => rows.map((t) => t[1]);

describe("tag search", () => {
  test("whole name first, then the start of the name, then the start of a word, then anywhere", () => {
    expect(names(searchTags(TAGS, "roguelike"))).toEqual(["Roguelike", "Action Roguelike"]);
    expect(names(searchTags(TAGS, "multi"))).toEqual(["Multiplayer", "Local Multiplayer"]);
    expect(names(searchTags(TAGS, "player"))).toEqual(["Singleplayer", "Multiplayer", "Local Multiplayer"]);
  });

  test("within a rank, the most used tags come first", () => {
    expect(names(searchTags(TAGS, "rogue"))).toEqual(["Roguelite", "Roguelike", "Action Roguelike"]);
  });

  test("case and surrounding spaces do not matter", () => {
    expect(names(searchTags(TAGS, "  SHOOT "))).toEqual(["Shooter"]);
    expect(names(searchTags(TAGS, "fps"))).toEqual(["FPS"]);
  });

  test("picked tags and tags without a name are left out", () => {
    expect(names(searchTags(TAGS, "rogue", { exclude: [3959] }))).toEqual(["Roguelike", "Action Roguelike"]);
    expect(searchTags(TAGS, "").some((t) => t[1] === null)).toBe(false);
  });

  test("an empty query lists the most used tags, up to the limit", () => {
    expect(SHOWN).toBe(8);
    expect(names(searchTags(TAGS, "", { limit: 3 }))).toEqual(["Singleplayer", "Action", "Multiplayer"]);
    expect(searchTags(TAGS, "")).toHaveLength(SHOWN);
  });

  test("no match gives an empty list", () => {
    expect(searchTags(TAGS, "zzz")).toEqual([]);
  });

  test("punctuation splits words, so the part after a hyphen is a word start", () => {
    const tags = [
      [1, "Rogue-lite", 10, 10],
      [2, "Satellite", 10, 10],
    ];
    expect(names(searchTags(tags, "lite"))).toEqual(["Rogue-lite", "Satellite"]);
  });

  test("tagNames maps ids to names, the id standing in for a missing name", () => {
    const map = tagNames(TAGS);
    expect(map.get(1774)).toBe("Shooter");
    expect(map.get(99999)).toBe("99999");
  });
});

describe("Chinese tag names", () => {
  const ZH = [
    [1716, "Roguelike", 900, 4500, "类 Rogue"],
    [3959, "Roguelite", 1300, 5200, "轻度 Rogue"],
    [42804, "Action Roguelike", 1100, 4800, "动作类 Rogue"],
    [1663, "FPS", 900, 4000, "第一人称射击"],
    [3871, "2D", 800, 3000, "2D"],
    [7368, "Local Multiplayer", 500, 3000, null], // no Chinese name in the data yet
  ];
  const shown = (rows) => rows.map((t) => tagName(t, zh));

  test("the Chinese page shows Steam's Chinese name, else the English one", () => {
    expect(shown(ZH)).toEqual(["类 Rogue", "轻度 Rogue", "动作类 Rogue", "第一人称射击", "2D", "Local Multiplayer"]);
    expect(tagNames(ZH, zh).get(1663)).toBe("第一人称射击");
    expect(tagNames(ZH).get(1663)).toBe("FPS"); // the English page
  });

  test("search finds a tag by its Chinese or its English name", () => {
    expect(shown(searchTags(ZH, "射击", { s: zh }))).toEqual(["第一人称射击"]);
    expect(shown(searchTags(ZH, "fps", { s: zh }))).toEqual(["第一人称射击"]);
    expect(shown(searchTags(ZH, "roguelike", { s: zh }))).toEqual(["类 Rogue", "动作类 Rogue"]);
    expect(shown(searchTags(ZH, "local", { s: zh }))).toEqual(["Local Multiplayer"]);
  });

  test("the better of the two matches decides the order", () => {
    // "rogue": a word start in every Chinese name, the start of two English names
    expect(shown(searchTags(ZH, "rogue", { s: zh }))).toEqual(["轻度 Rogue", "类 Rogue", "动作类 Rogue"]);
  });

  test("the English page does not search the Chinese names", () => {
    expect(searchTags(ZH, "射击")).toEqual([]);
  });
});
