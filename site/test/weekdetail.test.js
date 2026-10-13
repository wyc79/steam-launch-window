import { describe, expect, test } from "vitest";
import { weekGames } from "../src/lib/heatmap.js";
import { en } from "../src/strings.js";
import { dateText, detailItems, FIRST, followersText, listParts, movedText, storeUrl } from "../src/weekdetail.js";

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
  expect(dateText({ precision: "day", date: "2026-10-21" })).toBe("Oct 21");
  expect(dateText({ precision: "month", date: "2026-11-01" })).toBe("Nov 2026");
  expect(dateText({ precision: "quarter", date: "2026-10-01" })).toBe("Q4 2026");
  expect(dateText({ precision: "quarter", date: "2027-01-01" })).toBe("Q1 2027");
  expect(dateText({ precision: "year", date: "2027-01-01" })).toBe("2027");
  expect(dateText(undefined)).toBeNull();
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
    const items = detailItems(list, (id) => byId.get(id));
    expect(items.map((i) => i.appid)).toEqual(list.map((g) => g.appid)); // not re-sorted
    expect(items).toEqual([
      {
        appid: 2,
        name: "App 2",
        url: "https://store.steampowered.com/app/2/",
        part: "spread",
        date: "Oct 2026",
        followers: "about 5,000 followers, estimated from wishlist rank",
        moved: null,
      },
      {
        appid: 3,
        name: "Alpha",
        url: "https://store.steampowered.com/app/3/",
        part: "year",
        date: "2026",
        followers: "120 followers",
        moved: null,
      },
      {
        appid: 1,
        name: "Zed",
        url: "https://store.steampowered.com/app/1/",
        part: "exact",
        date: "Oct 21",
        followers: null,
        moved: "moved here from October 2026, 3 days ago",
      },
    ]);
  });

  test("leave the year layer out unless it is on", () => {
    const list = weekGames(games, "2026-10-13", "2026-10-19", { selection: [1] });
    expect(detailItems(list, (id) => byId.get(id), en).map((i) => i.part)).toEqual(["spread", "exact"]);
  });
});

describe("the list in parts", () => {
  const item = (appid, part) => ({ appid, part });
  const items = [
    item(1, "spread"),
    ...Array.from({ length: 30 }, (_, i) => item(100 + i, "exact")),
    ...Array.from({ length: 25 }, (_, i) => item(200 + i, "spread")),
    item(2, "year"),
  ];

  test("exact dates first and always in full, each part in the given order", () => {
    const parts = listParts(items);
    expect(parts.map((p) => [p.part, p.heading, p.items.length, p.total])).toEqual([
      ["exact", "Exact dates (30)", 30, 30],
      ["spread", "Month or quarter dates (26)", FIRST, 26],
    ]);
    expect(parts[1].items[0].appid).toBe(1); // not re-sorted
  });

  test("a part opened in full, and the year part with the year layer", () => {
    const parts = listParts(items, { year: true, open: new Set(["spread"]) });
    expect(parts.map((p) => [p.heading, p.items.length])).toEqual([
      ["Exact dates (30)", 30],
      ["Month or quarter dates (26)", 26],
      ["Year only (1)", 1],
    ]);
  });

  test("empty parts are left out", () => {
    expect(listParts([item(1, "exact")]).map((p) => p.part)).toEqual(["exact"]);
    expect(listParts([])).toEqual([]);
  });
});
