// Competition ahead drawn into a small stand-in DOM (test/fakedom.js): the text a
// reader sees, the week list in parts, and the page without events.json.

import { beforeEach, describe, expect, test } from "vitest";
import { children, fill, h } from "../src/ui/dom.js";
import { installDom } from "./fakedom.js";

installDom();
const { aheadSection } = await import("../src/ui/ahead.js");
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

  test("lists exact dates in full first, then month or quarter dates up to 20", () => {
    const parts = body.querySelectorAll(".ah-part");
    expect(parts.map((p) => p.querySelector("h4").textContent)).toEqual([
      "Exact dates (2)",
      "Month or quarter dates (25)",
    ]);
    expect(parts[0].querySelectorAll("li")).toHaveLength(2);
    expect(parts[0].textContent).toContain("moved here from Q4 2026, 1 day ago");
    expect(parts[1].querySelectorAll("li")).toHaveLength(20);
    parts[1].querySelector(".ah-more").click();
    expect(body.querySelectorAll(".ah-part")[1].querySelectorAll("li")).toHaveLength(25);
    expect(body.querySelector(".ah-more")).toBeNull();
  });

  test("is announced with its row", () => {
    expect(body.querySelector("p.visually-hidden").textContent).toBe("Horror, Week of Oct 19 to Oct 25. 27 games in this week.");
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

  test("names the typical week in the row head", () => {
    const body = draw();
    expect(body.querySelector(".hm-row-note").textContent).toBe("about 1.0 launches in a typical week");
  });

  test("draws no trend line when the niche's share is as usual", () => {
    expect(draw().querySelector(".ah-trend").textContent).toBe("");
  });

  test("names a niche whose share of upcoming games differs clearly, with its caveat", () => {
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
    expect(body.querySelectorAll(".ah-trend p").map((p) => p.textContent)).toEqual([
      "Horror is 2.0x as large a share of upcoming games (exact dates) as of last year's launches.",
      "Announced games: not all will launch.",
    ]);
  });

  test("without events.json, draws the heatmap and says the lanes are missing", () => {
    const body = draw(null);
    expect(body.querySelectorAll(".hm-cell").length).toBeGreaterThan(0);
    expect(body.querySelector(".hm-band-label")).toBeNull();
    expect(body.querySelector(".ah-events-note").textContent).toBe(en.ahead.eventsFailed);
  });
});
