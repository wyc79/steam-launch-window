import { describe, expect, test } from "vitest";
import { bandEvents, eventName, kindOf, shortName, shows, span, weekEvents } from "../src/events.js";
import { EVENT_NAMES_ZH } from "../src/eventnames.zh.js";
import { zh } from "../src/strings.js";
import { toDay } from "../src/lib/dates.js";

// events.json rows (pipeline/events.py fields), Pacific dates
const ev = (name, type, start, end, extra = {}) => ({ name, type, start, end, confidence: "high", ...extra });
const SALE = ev("Steam Winter Sale 2026", "seasonal_sale", "2026-12-17", "2027-01-04");
const FEST = ev("Steam Next Fest October 2026", "next_fest", "2026-10-19", "2026-10-26");
const HORROR = ev("Steam Scream V Fest 2026", "themed_fest", "2026-10-26", "2026-11-02", { tags: ["Horror"] });
const ROBOTS = ev("Steam Dinos vs. Robots Fest 2027", "themed_fest", "2027-03-29", "2027-04-05", { tags: ["Dinosaurs", "Robots"] });
const NO_TAGS = ev("Steam Sheep Fest 2027", "themed_fest", "2027-02-04", "2027-02-08");
const SPRING = ev("China Spring Festival holiday 2027", "regional_holiday", "2027-02-05", "2027-02-11", {
  region: "CN",
  confidence: "low",
});
const THANKS = ev("US Thanksgiving to Cyber Monday 2026", "regional_holiday", "2026-11-26", "2026-11-30", { region: "US" });
const XMAS = ev("Christmas to New Year 2026", "regional_holiday", "2026-12-24", "2027-01-01", { region: "global" });
const RELEASE = ev("Big Game", "major_release", "2026-11-05", "2026-11-05", { steam_appid: 1 });
const ALL = [FEST, HORROR, THANKS, SALE, XMAS, NO_TAGS, SPRING, ROBOTS, RELEASE];

describe("which events the band shows", () => {
  test("sales and Next Fests always", () => {
    expect(shows(SALE)).toBe(true);
    expect(shows(FEST, { tagNames: ["Puzzle"], languages: [] })).toBe(true);
  });

  test("a themed fest when one of the picked tags is among its tags, in any case", () => {
    expect(shows(HORROR, { tagNames: ["Horror"] })).toBe(true);
    expect(shows(HORROR, { tagNames: ["Puzzle", "horror"] })).toBe(true);
    expect(shows(ROBOTS, { tagNames: ["Robots"] })).toBe(true);
    expect(shows(HORROR, { tagNames: ["Puzzle"] })).toBe(false);
  });

  test("no themed fest without picked tags, and never one without tags (as in the model)", () => {
    expect(shows(HORROR, { tagNames: [] })).toBe(false);
    expect(shows(NO_TAGS, { tagNames: ["Sheep", "Horror"] })).toBe(false);
  });

  test("China's holidays only with Simplified Chinese picked", () => {
    expect(shows(SPRING, { languages: ["english"] })).toBe(false);
    expect(shows(SPRING, { languages: [] })).toBe(false); // any language is not a pick of Chinese
    expect(shows(SPRING, { languages: ["english", "schinese"] })).toBe(true);
  });

  test("never releases, US or Western holidays", () => {
    const all = { tagNames: ["Horror"], languages: ["schinese"] };
    for (const e of [THANKS, XMAS, RELEASE]) expect(shows(e, all)).toBe(false);
    expect(kindOf(THANKS)).toBeNull();
    expect(kindOf(SPRING)).toBe("cn_holiday");
  });
});

describe("when an event is in effect", () => {
  test("Steam events run 10:00 to 10:00 Pacific", () => {
    expect(span(FEST)).toEqual([toDay("2026-10-19") + 10 / 24, toDay("2026-10-26") + 10 / 24]);
  });

  test("holidays cover whole days, the end included", () => {
    expect(span(SPRING)).toEqual([toDay("2027-02-05"), toDay("2027-02-12")]);
  });
});

test("short names drop Steam and the year", () => {
  expect(shortName("Steam Next Fest October 2026")).toBe("Next Fest October");
  expect(shortName("China Spring Festival holiday 2027")).toBe("China Spring Festival holiday");
  expect(shortName("Steam Dinos vs. Robots Fest 2027")).toBe("Dinos vs. Robots Fest");
});

describe("the band for 26 weeks from Monday 2026-10-12", () => {
  const pick = { tagNames: ["Horror", "Robots"], languages: ["english", "schinese"] };

  test("keeps the shown events inside the weeks, in time order, with their flags", () => {
    const { events } = bandEvents(ALL, "2026-10-12", 26, pick);
    expect(events.map((e) => e.name)).toEqual([
      FEST.name,
      HORROR.name,
      SALE.name,
      SPRING.name,
      ROBOTS.name,
    ]);
    const spring = events.find((e) => e.kind === "cn_holiday");
    expect(spring).toMatchObject({ unconfirmed: true, estimate: false });
    expect(events.find((e) => e.kind === "seasonal_sale")).toMatchObject({ unconfirmed: false, estimate: false });
  });

  test("leaves out events after the last week or before the first", () => {
    const { events } = bandEvents(ALL, "2026-10-12", 4, pick);
    expect(events.map((e) => e.name)).toEqual([FEST.name, HORROR.name]);
    const before = ev("Steam Autumn Sale 2026", "seasonal_sale", "2026-09-30", "2026-10-07");
    expect(bandEvents([before], "2026-10-12", 26).events).toEqual([]);
  });

  test("marks other low-confidence events as estimated dates", () => {
    const guess = { ...SALE, confidence: "low" };
    expect(bandEvents([guess], "2026-10-12", 26).events[0].estimate).toBe(true);
  });

  test("gives each kind its lane, and overlapping events of a kind a second row", () => {
    const other = ev("Steam Ghost Fest 2026", "themed_fest", "2026-10-28", "2026-11-04", { tags: ["Horror"] });
    const { events, lanes } = bandEvents([...ALL, other], "2026-10-12", 26, pick);
    expect(lanes).toEqual([
      { kind: "seasonal_sale", row: 0 },
      { kind: "next_fest", row: 0 },
      { kind: "themed_fest", row: 0 },
      { kind: "themed_fest", row: 1 },
      { kind: "cn_holiday", row: 0 },
    ]);
    const lane = (name) => lanes[events.find((e) => e.name === name).lane];
    expect(lane(HORROR.name)).toEqual({ kind: "themed_fest", row: 0 });
    expect(lane(other.name)).toEqual({ kind: "themed_fest", row: 1 });
    expect(lane(ROBOTS.name)).toEqual({ kind: "themed_fest", row: 0 }); // the first row is free again by March
  });

  test("know the weeks they cover, and how far their name may run", () => {
    const { events } = bandEvents(ALL, "2026-10-12", 13, pick);
    const of = (name) => events.find((e) => e.name === name);
    expect(of(FEST.name).weeks).toEqual([1, 1]); // Oct 19 10:00 to Oct 26 10:00: not the week of Oct 26
    expect(of(SALE.name).weeks).toEqual([9, 11]); // Dec 17 to Jan 4 10:00
    expect(of(FEST.name).room).toBe(13); // nothing after it in its lane
    const later = ev("Steam Next Fest December 2026", "next_fest", "2026-12-07", "2026-12-14");
    const two = bandEvents([FEST, later], "2026-10-12", 13).events;
    expect(two.map((e) => [e.weeks[0], e.room])).toEqual([
      [1, 8],
      [8, 13],
    ]);
  });

  test("events of a kind sharing a week go to two rows, even without overlapping in time", () => {
    const early = ev("Steam Bat Fest 2026", "themed_fest", "2026-10-26", "2026-10-28", { tags: ["Horror"] });
    const late = ev("Steam Owl Fest 2026", "themed_fest", "2026-10-29", "2026-10-31", { tags: ["Horror"] });
    const { events } = bandEvents([early, late], "2026-10-12", 13, { tagNames: ["Horror"] });
    expect(events.map((e) => [e.weeks, e.row])).toEqual([
      [[2, 2], 0],
      [[2, 2], 1],
    ]);
  });

  test("leave out an event that covers less than a day of any week shown", () => {
    const edge = ev("Steam Edge Sale 2027", "seasonal_sale", "2027-01-08", "2027-01-11");
    expect(bandEvents([edge], "2026-10-12", 13).events).toHaveLength(1); // Jan 8 to 11: in the 13th week
    const after = ev("Steam After Sale 2027", "seasonal_sale", "2027-01-11", "2027-01-18");
    expect(bandEvents([after], "2026-10-12", 13).events).toEqual([]);
  });
});

describe("the events in a week", () => {
  const { events } = bandEvents(ALL, "2026-10-12", 26, { tagNames: ["Horror"], languages: ["schinese"] });

  test("a Steam event ending Monday 10:00 is not in that week too", () => {
    expect(weekEvents(events, "2026-10-19").map((e) => e.name)).toEqual([FEST.name]);
    expect(weekEvents(events, "2026-10-26").map((e) => e.name)).toEqual([HORROR.name]);
  });

  test("a holiday over a weekend counts in both weeks", () => {
    expect(weekEvents(events, "2027-02-01").map((e) => e.name)).toEqual([SPRING.name]);
    expect(weekEvents(events, "2027-02-08").map((e) => e.name)).toEqual([SPRING.name]);
  });

  test("a long sale is in every week it covers", () => {
    for (const week of ["2026-12-14", "2026-12-21", "2026-12-28"]) {
      expect(weekEvents(events, week).map((e) => e.name)).toContain(SALE.name);
    }
    expect(weekEvents(events, "2027-01-04").map((e) => e.name)).not.toContain(SALE.name);
  });
});

describe("names on the Chinese page", () => {
  test("Steam's Chinese names, with the year where Steam puts it", () => {
    expect(eventName("Steam Winter Sale 2026", zh)).toBe("2026 年 Steam 冬季特卖");
    expect(eventName("Steam Next Fest October 2026", zh)).toBe("Steam 新品节：2026 年 10 月版");
    expect(eventName("China Spring Festival holiday 2027", zh)).toBe("2027 年春节假期");
  });

  test("short names drop Steam and the year", () => {
    expect(eventName("Steam Dinos vs. Robots Fest 2027", zh, { short: true })).toBe("恐龙大战机器人游戏节");
    expect(eventName("Steam Next Fest October 2026", zh, { short: true })).toBe("新品节：10 月版");
    expect(eventName("Steam Next Fest October", zh, { short: true })).toBe("新品节：10 月版"); // a series
    expect(eventName("Christmas to New Year 2026", zh, { short: true })).toBe("圣诞节至元旦");
  });

  test("a release keeps its English name, and the English page is unchanged", () => {
    expect(eventName("Grand Theft Auto VI", zh)).toBe("Grand Theft Auto VI");
    expect(eventName("Steam Winter Sale 2026")).toBe("Steam Winter Sale 2026");
    expect(eventName("Steam Winter Sale 2026", undefined, { short: true })).toBe("Winter Sale");
  });

  test("every Steam event and holiday in events.yaml has a Chinese name", async () => {
    const { readFileSync } = await import("node:fs");
    const yaml = readFileSync(new URL("../../data/events.yaml", import.meta.url), "utf8");
    const entries = yaml
      .split(/\r?\n- name: /)
      .slice(1)
      .map((e) => [e.split(/\r?\n/)[0].replace(/^'(.*)'$/, "$1"), e.match(/\n {2}type: (\w+)/)[1]]);
    const missing = entries
      .filter(([, type]) => type !== "major_release")
      .map(([name]) => name.replace(/ \d{4}$/, ""))
      .filter((series) => !EVENT_NAMES_ZH[series]);
    expect(entries.length).toBeGreaterThan(100);
    expect([...new Set(missing)]).toEqual([]);
  });
});
