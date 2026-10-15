import { describe, expect, test } from "vitest";
import { weekGames } from "../src/lib/heatmap.js";
import { en } from "../src/strings.js";
import {
  dateText,
  detailItems,
  findGames,
  fold,
  followersText,
  fullDate,
  listParts,
  movedText,
  steamDate,
  storeUrl,
  tagPosText,
} from "../src/weekdetail.js";

describe("where the picked tags sit", () => {
  const names = new Map([
    [4158, "Beat 'em up"],
    [492, "Roguelike"],
  ]);

  test("one tag: its place of the game's tags", () => {
    expect(tagPosText([[4158, 6]], 20, names)).toBe("Beat 'em up: tag 6 of 20");
  });

  test("several tags: each one in the one-tag form, joined with the bar's separator", () => {
    expect(tagPosText([[4158, 6], [492, 12]], 20, names)).toBe("Beat 'em up: tag 6 of 20 · Roguelike: tag 12 of 20");
  });

  test("an unnamed tag shows its id; nothing when no tags are picked", () => {
    expect(tagPosText([[7, 1]], 3, names)).toBe("7: tag 1 of 3");
    expect(tagPosText([], 20, names)).toBeNull();
    expect(tagPosText(undefined, 20, names)).toBeNull();
  });
});

describe("the moved marker", () => {
  test("says where the game came from and when", () => {
    expect(movedText(["moved", "October 2026", 3])).toBe("moved here from October 2026, 3 days ago");
    expect(movedText(["moved", "Q4 2026", 1])).toBe("moved here from Q4 2026, 1 day ago");
    expect(movedText(["moved", "2026", 0])).toBe("moved here from 2026, today");
  });

  test("a game that had no date says its date was just set", () => {
    expect(movedText(["date_set", "Coming soon", 2])).toBe("date just set, 2 days ago");
  });

  test("nothing when the date did not change", () => {
    expect(movedText(null)).toBeNull();
  });
});

describe("followers", () => {
  test("a count, or an estimate from wishlist rank marked as one", () => {
    expect(followersText(12400, "f")).toBe("12,400 followers");
    expect(followersText(3100, "r")).toBe("about 3,100 followers, estimated from wishlist rank");
  });

  test("nothing when unknown", () => {
    expect(followersText(null, null)).toBeNull();
  });
});

test("dates as the store gives them", () => {
  expect(dateText({ precision: "day", date: "2026-10-21" })).toBe("10/21");
  expect(dateText({ precision: "month", date: "2026-11-01" })).toBe("11/2026");
  expect(dateText({ precision: "quarter", date: "2026-10-01" })).toBe("Q4 2026");
  expect(dateText({ precision: "quarter", date: "2027-01-01" })).toBe("Q1 2027");
  expect(dateText({ precision: "year", date: "2027-01-01" })).toBe("2027");
  expect(dateText(undefined)).toBeNull();
});

test("dates as the store page shows them, year included, for the most anticipated list", () => {
  expect(steamDate({ precision: "day", date: "2026-10-28" })).toBe("10/28/2026");
  expect(steamDate({ precision: "month", date: "2026-12-01" })).toBe("12/2026");
  expect(steamDate({ precision: "quarter", date: "2027-01-01" })).toBe("Q1 2027");
  expect(steamDate({ precision: "year", date: "2027-01-01" })).toBe("2027");
  expect(steamDate({ precision: "day", date: "2026-09-30" })).toBe("9/30/2026"); // passed, still as the store has it
  expect(fullDate("2026-10-13")).toBe("10/13/2026");
});

test("a game with no date shows the store's own words, else To be announced", () => {
  expect(steamDate({ precision: "unknown", date: null, date_text: "Coming soon" })).toBe("Coming soon");
  expect(steamDate({ precision: "unknown", date: null, date_text: "To be announced" })).toBe("To be announced");
  expect(steamDate({ precision: "unknown", date: null, date_text: null })).toBe("To be announced");
  expect(steamDate({ precision: "unknown", date: null })).toBe("To be announced");
  // the week list's dates are untouched: it lists only games with a date
  expect(dateText({ precision: "unknown", date: null, date_text: "Coming soon" })).toBeNull();
});

test("store links", () => {
  expect(storeUrl(620)).toBe("https://store.steampowered.com/app/620/");
});

describe("a week's games", () => {
  const up = (appid, name, precision, date, date_end, extra = {}) => ({
    appid,
    name,
    tags: [1],
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
  const games = [
    up(1, "Zed", "day", "2026-10-21", "2026-10-21", { moved: ["moved", "October 2026", "2026-10-10"] }),
    up(2, "", "month", "2026-10-01", "2026-10-31", { followers: 5000, hype_src: "r" }),
    up(3, "Alpha", "year", "2026-01-01", "2026-12-31", { followers: 120, hype_src: "f" }),
  ];
  const byId = new Map(games.map((g) => [g.appid, g]));

  test("keep weekGames' order and format each line", () => {
    const list = weekGames(games, "2026-10-13", "2026-10-19", { selection: [1], year: true });
    const items = detailItems(list, (id) => byId.get(id), en, new Map([[1, "Horror"]]));
    expect(items.map((i) => i.appid)).toEqual(list.map((g) => g.appid)); // not re-sorted
    expect(items).toEqual([
      {
        appid: 2,
        name: "App 2",
        url: "https://store.steampowered.com/app/2/",
        share: expect.closeTo(7 / 19, 12),
        part: "spread",
        date: "10/2026",
        followers: "about 5,000 followers, estimated from wishlist rank",
        moved: null,
        tagPos: "Horror: tag 1 of 1",
      },
      {
        appid: 3,
        name: "Alpha",
        url: "https://store.steampowered.com/app/3/",
        share: expect.closeTo(7 / 80, 12),
        part: "year",
        date: "2026",
        followers: "120 followers",
        moved: null,
        tagPos: "Horror: tag 1 of 1",
      },
      {
        appid: 1,
        name: "Zed",
        url: "https://store.steampowered.com/app/1/",
        share: 1,
        part: "exact",
        date: "10/21",
        followers: null,
        moved: "moved here from October 2026, 3 days ago",
        tagPos: "Horror: tag 1 of 1",
      },
    ]);
  });

  test("no tag places when no tags are picked", () => {
    const list = weekGames(games, "2026-10-13", "2026-10-19", { year: true });
    expect(detailItems(list, (id) => byId.get(id)).map((i) => i.tagPos)).toEqual([null, null, null]);
  });

  test("leave the year layer out unless it is on", () => {
    const list = weekGames(games, "2026-10-13", "2026-10-19", { selection: [1] });
    expect(detailItems(list, (id) => byId.get(id), en).map((i) => i.part)).toEqual(["spread", "exact"]);
  });
});

describe("the list in parts", () => {
  const item = (appid, part, name = `Game ${appid}`) => ({ appid, part, name });
  const items = [
    item(1, "spread"),
    ...Array.from({ length: 30 }, (_, i) => item(100 + i, "exact")),
    ...Array.from({ length: 25 }, (_, i) => item(200 + i, "spread")),
    item(2, "year"),
  ];

  test("exact dates first, every part in full and in the given order", () => {
    const parts = listParts(items);
    expect(parts.map((p) => [p.part, p.heading, p.items.length])).toEqual([
      ["exact", "Exact dates (30)", 30],
      ["spread", "Month or quarter dates (26, together 26 games' worth)", 26], // no shares given: 1 each
    ]);
    expect(parts[1].items[0].appid).toBe(1); // not re-sorted
    expect(listParts(items, { year: true }).at(-1).heading).toBe("Year only (1, together 1 game's worth)");
  });

  test("empty parts are left out", () => {
    expect(listParts([item(1, "exact")]).map((p) => p.part)).toEqual(["exact"]);
    expect(listParts([])).toEqual([]);
  });
});

describe("finding a game in the week", () => {
  const games = [
    { name: "Pokémon Café", part: "spread" },
    { name: "POKER NIGHT", part: "exact" },
    { name: "Hollow Knight", part: "exact" },
  ];

  test("by name, case and accents aside, keeping the order", () => {
    expect(findGames(games, "poke").map((g) => g.name)).toEqual(["Pokémon Café", "POKER NIGHT"]);
    expect(findGames(games, "  CAFE ").map((g) => g.name)).toEqual(["Pokémon Café"]);
    expect(findGames(games, "")).toBe(games);
    expect(findGames(games, "zzz")).toEqual([]);
    expect(fold("Ëxtrême")).toBe("extreme");
  });

  test("exact-date games that match stay listed first", () => {
    const parts = listParts(findGames(games, "o"));
    expect(parts.map((p) => [p.part, p.items.map((g) => g.name)])).toEqual([
      ["exact", ["POKER NIGHT", "Hollow Knight"]],
      ["spread", ["Pokémon Café"]],
    ]);
  });
});
