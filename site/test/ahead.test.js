// Competition ahead drawn into a small stand-in DOM (test/fakedom.js): the text a
// reader sees, the week list in parts, and the page without events.json.

import { beforeEach, describe, expect, test } from "vitest";
import { children, fill, h } from "../src/ui/dom.js";
import { installDom } from "./fakedom.js";

installDom();
const { aheadSection, SHOW_TREND } = await import("../src/ui/ahead.js");
const { trendLines } = await import("../src/heatview.js");
const { createNumbers } = await import("../src/numbers.js");
const { DEFAULT } = await import("../src/state.js");
const { en } = await import("../src/strings.js");

const TODAY = "2026-10-13"; // the first week starts Monday Oct 12
const game = (appid, precision, date, date_end, extra = {}) => ({
  appid,
  name: `Game ${appid}`,
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
// week of Oct 19: 2 exact dates and 25 October games spread over it; no events in it
const GAMES = [
  game(1, "day", "2026-10-20", "2026-10-20", { moved: ["moved", "Q4 2026", "2026-10-12"] }),
  game(2, "day", "2026-10-21", "2026-10-21"),
  ...Array.from({ length: 25 }, (_, i) => game(100 + i, "month", "2026-10-01", "2026-10-31")),
];
// 52 launches in the last 52 weeks: a typical week of one launch
const HISTORY = Array.from({ length: 52 }, (_, i) => ({
  tags: [1],
  langs: ["english"],
  free: false,
  launch_type: "full",
  launch_date: new Date(Date.UTC(2025, 9, 20) + i * 7 * 86400000).toISOString().slice(0, 10),
}));
const META = { snapshot_date: TODAY, tags: [[1, "Horror", 27, 52]], languages: ["english"] };
const FEST = { name: "Steam Scream V Fest 2026", type: "themed_fest", start: "2026-10-26", end: "2026-11-02", tags: ["Horror"] };

function draw(events = [FEST]) {
  const body = h("div");
  const section = aheadSection(en, body);
  section.start(createNumbers(GAMES, HISTORY, TODAY), META);
  section.setEvents(events);
  section.draw({ ...DEFAULT, tags: [1] });
  return body;
}

describe("dom helpers", () => {
  test("skip null, undefined and false, as h() does", () => {
    expect(children("a", [null, ["b", false]], undefined, 0)).toEqual(["a", "b", 0]);
    const el = fill(h("p"), "x", false, null, h("span", {}, "y", false));
    expect(el.textContent).toBe("xy");
  });
});

describe("an opened week", () => {
  let body;
  beforeEach(() => {
    body = draw();
    body.querySelectorAll(".hm-cell")[1].click(); // Horror, week of Oct 19
  });

  test("never shows the words false or null", () => {
    const text = body.querySelector(".ah-detail").textContent;
    expect(text).toContain("Week of Oct 19 to Oct 25");
    expect(text).not.toMatch(/false|null|undefined/);
  });

  test("lists every game in a labelled scroll area, exact dates first", () => {
    const list = body.querySelector(".ah-list");
    expect([list.getAttribute("role"), list.getAttribute("tabindex"), list.getAttribute("aria-label")]).toEqual([
      "region",
      "0",
      "Games in the week of Oct 19 to Oct 25",
    ]);
    const parts = list.querySelectorAll(".ah-part");
    expect(parts.map((p) => p.querySelector("h4").textContent)).toEqual([
      "Exact dates (2)",
      "Month or quarter dates (25, together about 9.2 games' worth)",
    ]);
    expect(parts[0].querySelectorAll("li")).toHaveLength(2);
    expect(parts[0].textContent).toContain("moved here from Q4 2026, 1 day ago");
    expect(parts[1].querySelectorAll("li")).toHaveLength(25);
    expect(body.querySelector(".ah-found").textContent).toBe("27 of 27 games");
  });

  test("a search filters the list as you type, with a live count, and resets for another week", () => {
    const search = body.querySelector(".ah-search");
    search.value = "GAME 1";
    search.dispatch("input");
    // Game 1 and Game 100 to 124 match; Game 2 does not
    expect(body.querySelector(".ah-found").textContent).toBe("26 of 27 games");
    expect(body.querySelector(".ah-found").getAttribute("aria-live")).toBe("polite");
    expect(body.querySelectorAll(".ah-list .ah-part h4").map((x) => x.textContent)).toEqual([
      "Exact dates (1)",
      "Month or quarter dates (25, together about 9.2 games' worth)",
    ]);
    search.value = "nothing like this";
    search.dispatch("input");
    expect(body.querySelector(".ah-found").textContent).toBe("0 of 27 games");
    expect(body.querySelector(".ah-none").textContent).toBe(en.ahead.noMatch);
    body.querySelectorAll(".hm-cell")[2].click(); // another week
    expect(body.querySelector(".ah-search").getAttribute("value")).toBe("");
  });

  test("is announced with its row", () => {
    expect(body.querySelector("p.visually-hidden").textContent).toBe(
      "Horror, Week of Oct 19 to Oct 25. 27 games listed: 2 with exact dates · 25 dated only by month or quarter (together about 9.2 games' worth) · 1 in a typical week.",
    );
  });

  test("says how the cell's parts add up, from the cell's own numbers", () => {
    // 2 exact dates and 25 October games, each adding its share of this week (9.2 in all)
    expect(body.querySelector(".ah-detail-how").textContent).toBe(
      "A month or quarter date is divided across the weeks it covers. Exact and spread are each compared with the same typical week, so they add up: 2.0 + 9.2 = about 11 typical weeks.",
    );
  });

  test("a cell shows its raw numbers on hover or focus, and Escape hides them", () => {
    const cell = body.querySelectorAll(".hm-cell")[1];
    cell.dispatch("pointerenter", { pointerType: "mouse" });
    const tip = body.querySelector(".hm-tip");
    expect(tip.hidden).toBe(false);
    expect(tip.textContent).toBe(
      "Week of Oct 19: 2 with exact dates, about 9.2 games' worth from month or quarter dates, 1 in a typical week.",
    );
    expect(cell.getAttribute("aria-label")).toContain(tip.textContent);
    cell.dispatch("pointerleave");
    expect(tip.hidden).toBe(true);
    cell.dispatch("pointerenter", { pointerType: "touch" }); // a tap opens the week instead
    expect(tip.hidden).toBe(true);
  });
});

describe("what past launches during an event did", () => {
  const MODEL = {
    paid: {
      status: "ok",
      headline: "reviews",
      reviews: { effects: [{ key: "themed_fest", rate_ratio: 0.5476, low: 0.4618, high: 0.6495, p: 0.001 }] },
      chance_test: { themed_fest: { p_value: 0.04, ratio_alone: 0.56, windows: 69 } },
    },
    free: { status: "unreliable" },
  };
  function drawWith(model, group = "paid") {
    const body = h("div");
    const section = aheadSection(en, body);
    section.start(createNumbers(GAMES, HISTORY, TODAY), META);
    section.setEvents([FEST]);
    section.setModel(model);
    section.draw({ ...DEFAULT, tags: [1], group });
    return body;
  }

  test("no row of its own: an advice event's effect goes in its block's tooltip and its week's label", () => {
    const body = drawWith(MODEL);
    expect(body.querySelector(".hm-like")).toBeNull();
    expect(body.querySelector(".hm-block-name").getAttribute("title")).toBe(
      "Steam Scream V Fest 2026, Oct 26 to Nov 2. Past paid launches during a themed fest matching their tags got 45% fewer reviews.",
    );
    expect(body.querySelector(".hm-block-name").textContent).toBe("Scream V Fest"); // no number drawn
    expect(body.querySelectorAll(".hm-week")[2].getAttribute("aria-label")).toContain(
      "Events: Steam Scream V Fest 2026. Past paid launches during a themed fest matching their tags got 45% fewer reviews.",
    );
  });

  test("the opened week's Events line carries the effect too (phones have no lanes)", () => {
    const body = drawWith(MODEL);
    body.querySelectorAll(".hm-cell")[2].click(); // the week of Oct 26
    expect(body.querySelector(".ah-detail-events").textContent).toContain(
      "Steam Scream V Fest 2026, Oct 26 to Nov 2. Past paid launches during a themed fest matching their tags got 45% fewer reviews.",
    );
  });

  test("a group whose model is not ready: the tooltip has only the event", () => {
    const body = drawWith({ ...MODEL, paid: { status: "unreliable" } });
    expect(body.querySelector(".hm-block-name").getAttribute("title")).toBe("Steam Scream V Fest 2026, Oct 26 to Nov 2");
  });
});

describe("the most anticipated list", () => {
  // ranked games at any date: undated, beyond the 13 weeks, and one in the week of Oct 19
  const RANKED = [
    game(201, "unknown", null, null, { wishlist_rank: 812, date_text: "Coming soon" }),
    game(202, "day", "2027-05-04", "2027-05-04", { wishlist_rank: 212 }),
    game(203, "quarter", "2027-01-01", "2027-03-31", { wishlist_rank: 4000, tags: [2] }),
    game(204, "month", "2026-12-01", "2026-12-31", { wishlist_rank: 1500, followers: 900, hype_src: "r" }),
    game(205, "year", "2027-01-01", "2027-12-31", { wishlist_rank: 3, free: true }),
    { ...GAMES[0], wishlist_rank: 2500, name: "" },
  ];
  const names = { ...META, tags: [...META.tags, [2, "Puzzle", 1, 0]] };
  function setup(patch = {}, games = [...RANKED, ...GAMES.slice(1)], meta = names) {
    const body = h("div");
    const section = aheadSection(en, body);
    section.start(createNumbers(games, HISTORY, TODAY), meta);
    section.setEvents([]);
    section.draw({ ...DEFAULT, ...patch });
    return { body, section };
  }
  const drawRanked = (...args) => setup(...args).body;
  const rows = (body) => body.querySelectorAll(".ah-top-list li");

  test("lists the picked group's matching games by rank, at any date, in an ordered list", () => {
    const body = drawRanked({ tags: [1] });
    expect(body.querySelector(".ah-top h3").textContent).toBe("Most anticipated in your niche");
    expect(body.querySelector(".ah-top-for").textContent).toBe("Horror, Paid, in English");
    expect(body.querySelector(".ah-top-list").tagName).toBe("OL");
    expect(rows(body).map((li) => li.querySelector(".ah-top-meta").textContent)).toEqual([
      "May 4, 2027 · #212 on Top Wishlisted",
      "Coming soon · #812 on Top Wishlisted", // the store's own words for a game with no date
      // ranked lower, so after #812 whatever its followers; and the followers are not shown
      "December 2026 · #1,500 on Top Wishlisted",
      "Oct 20, 2026 · #2,500 on Top Wishlisted",
    ]);
    expect(rows(body)[3].querySelector("a").textContent).toBe("App 1 (opens in a new tab)");
    expect(body.querySelector(".ah-top").textContent).not.toMatch(/follower/);
  });

  test("links open the store page in a new tab", () => {
    const link = rows(drawRanked({ tags: [1] }))[0].querySelector("a");
    expect(link.getAttribute("href")).toBe("https://store.steampowered.com/app/202/");
    expect([link.getAttribute("target"), link.getAttribute("rel")]).toEqual(["_blank", "noopener"]);
  });

  test("no tags: all games of the group, titled for all of Steam, with the snapshot date", () => {
    const body = drawRanked({ group: "free" });
    expect(body.querySelector(".ah-top h3").textContent).toBe("Most anticipated on Steam");
    expect(body.querySelector(".ah-top-for").textContent).toBe("All games, Free, in English");
    expect(rows(body)).toHaveLength(1);
    expect(body.querySelector(".ah-top-note").textContent).toBe(
      "Rank on Steam's Top Wishlisted list on Oct 13, 2026. Not wishlist counts.",
    );
  });

  test("the list is named by its title for screen readers", () => {
    const body = drawRanked();
    const id = body.querySelector(".ah-top h3").getAttribute("id");
    expect(id).toMatch(/^ah-top-title-\d+$/);
    expect(body.querySelector(".ah-top-list").getAttribute("aria-labelledby")).toBe(id);
    expect(drawRanked().querySelector(".ah-top h3").getAttribute("id")).not.toBe(id); // one per section
  });

  test("keeps the caveat without a snapshot date", () => {
    const body = drawRanked({}, undefined, { ...names, snapshot_date: undefined });
    expect(body.querySelector(".ah-top-note").textContent).toBe("Rank on Steam's Top Wishlisted list. Not wishlist counts.");
  });

  test("only languages picked: titled for all of Steam, the for-line names the group and the languages", () => {
    const chinese = game(207, "unknown", null, null, { wishlist_rank: 50, langs: ["schinese"], date_text: "To be announced" });
    const body = drawRanked({ languages: ["schinese"] }, [...RANKED, ...GAMES, chinese]);
    expect(body.querySelector(".ah-top h3").textContent).toBe("Most anticipated on Steam");
    expect(body.querySelector(".ah-top-for").textContent).toBe("All games, Paid, in Simplified Chinese");
    expect(rows(body).map((li) => li.querySelector("a").textContent)).toEqual(["Game 207 (opens in a new tab)"]);
  });

  test("a group switch on the same section replaces the list", () => {
    const { body, section } = setup();
    const paid = rows(body).map((li) => li.querySelector(".ah-top-meta").textContent);
    section.draw({ ...DEFAULT, group: "free" });
    expect(body.querySelector(".ah-top-for").textContent).toBe("All games, Free, in English");
    const free = rows(body).map((li) => li.querySelector(".ah-top-meta").textContent);
    expect(free).toEqual(["2027 · #3 on Top Wishlisted"]);
    expect(paid).not.toContain(free[0]);
  });

  test("a redraw for events or the model keeps the same links, so focus stays", () => {
    const { body, section } = setup({ tags: [1] });
    const links = rows(body).map((li) => li.querySelector("a"));
    section.setEvents([FEST]);
    section.setModel(null);
    section.draw({ ...DEFAULT, tags: [1] });
    expect(rows(body).every((li, i) => li.querySelector("a") === links[i])).toBe(true);
  });

  test("is hidden when no upcoming game matches, like the heatmap", () => {
    const body = drawRanked({ tags: [2], group: "free" }); // the Puzzle game is paid
    expect(body.querySelector(".ah-top").hidden).toBe(true);
    expect(body.querySelector(".ah-top").textContent).not.toMatch(/false|null|undefined|NaN/);
  });

  test("stops at 10", () => {
    const many = Array.from({ length: 14 }, (_, i) => game(300 + i, "unknown", null, null, { wishlist_rank: 14 - i }));
    const body = drawRanked({}, [...many, ...GAMES]);
    expect(rows(body)).toHaveLength(10);
    expect(rows(body)[0].querySelector(".ah-top-meta").textContent).toBe("To be announced · #1 on Top Wishlisted");
    expect(rows(body)[9].querySelector(".ah-top-meta").textContent).toBe("To be announced · #10 on Top Wishlisted");
  });

  test("one line when none of the matching games is ranked, or the snapshot has no ranks", () => {
    const unranked = game(206, "day", "2026-10-20", "2026-10-20", { tags: [2], free: true });
    const body = drawRanked({ tags: [2], group: "free" }, [...RANKED, unranked]);
    expect(body.querySelector(".ah-top").hidden).toBe(false);
    expect(body.querySelector(".ah-top-list")).toBeNull();
    expect(body.querySelector(".ah-top-none").textContent).toBe("No matching game is on Top Wishlisted.");
    expect(body.querySelector(".ah-top-note")).toBeNull();
    const plain = draw(); // the week tests' games have no ranks at all
    expect(plain.querySelector(".ah-top-none").textContent).toBe("This snapshot has no Top Wishlisted ranks.");
    expect(plain.querySelector(".ah-top-note")).toBeNull();
  });

  test("never shows the words false or null", () => {
    for (const patch of [{}, { tags: [1] }, { tags: [2] }, { group: "free" }]) {
      expect(drawRanked(patch).querySelector(".ah-top").textContent).not.toMatch(/false|null|undefined|NaN/);
    }
  });
});

describe("the grid", () => {
  test("puts the events lanes under the dates, with their own label", () => {
    const body = draw();
    expect(body.querySelector(".hm-band-label").textContent).toBe("Events");
    expect(body.querySelector(".hm-lane-name").textContent).toBe("Themed fests");
    expect(body.querySelector(".hm-block-name").textContent).toBe("Scream V Fest");
    expect(body.querySelector(".hm-block-name").getAttribute("title")).toBe("Steam Scream V Fest 2026, Oct 26 to Nov 2");
  });

  test("the legend has a swatch for each shade step, with the cells' classes", () => {
    const body = draw();
    const swatches = body.querySelectorAll(".ah-swatch .hm-part").map((el) => el.className);
    expect(swatches).toEqual(Array.from({ length: 8 }, (_, i) => `hm-part s${i}`));
  });

  test("with the year-only layer, the legend has a year swatch on each side of 1.0", () => {
    const body = draw();
    const input = body.querySelector(".ah-toggle input");
    input.checked = true;
    input.dispatch("change");
    const swatches = body.querySelectorAll(".ah-swatch");
    expect(swatches.slice(-2).map((el) => el.querySelector(".hm-part").className)).toEqual([
      "hm-part is-year s3",
      "hm-part is-year s4",
    ]);
    expect(swatches.slice(-2).map((el) => el.textContent)).toEqual(["Y <1.0", "Y 1.0+"]);
  });

  test("names the typical week in the row head", () => {
    const body = draw();
    expect(body.querySelector(".hm-row-note").textContent).toBe("about 1.0 launches in a typical week");
  });

  test("draws no trend line when the niche's share is as usual", () => {
    expect(draw().querySelector(".ah-trend").textContent).toBe("");
  });

  test("the trend line is held back: nothing drawn even for a clear niche", () => {
    // Horror: 20 of 40 upcoming games with exact dates, 52 of 208 past launches
    const games = Array.from({ length: 40 }, (_, i) =>
      game(500 + i, "day", "2026-10-20", "2026-10-20", { tags: i < 20 ? [1] : [2] }),
    );
    const history = Array.from({ length: 208 }, (_, i) => ({ ...HISTORY[i % 52], tags: i < 52 ? [1] : [2] }));
    const body = h("div");
    const section = aheadSection(en, body);
    section.start(createNumbers(games, history, TODAY), { ...META, tags: [...META.tags, [2, "Puzzle", 20, 156]] });
    section.setEvents([]);
    section.draw({ ...DEFAULT, tags: [1] });
    expect(SHOW_TREND).toBe(false);
    expect(body.querySelector(".ah-trend").textContent).toBe("");
    expect(trendLines(
      [{ label: "Horror" }],
      [createNumbers(games, history, TODAY).trend({ ...DEFAULT, tags: [1] })[0]],
      "paid",
      en,
    )).toEqual(["Horror is 2.0x as large a share of upcoming games (exact dates) as of last year's launches."]);
  });

  test("without events.json, draws the heatmap and says the lanes are missing", () => {
    const body = draw(null);
    expect(body.querySelectorAll(".hm-cell").length).toBeGreaterThan(0);
    expect(body.querySelector(".hm-band-label")).toBeNull();
    expect(body.querySelector(".ah-events-note").textContent).toBe(en.ahead.eventsFailed);
  });
});
