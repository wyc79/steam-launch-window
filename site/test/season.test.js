// Typical for this time of year, drawn into a small stand-in DOM (test/fakedom.js):
// it waits for events.json, draws 26 weeks as a listbox the arrow keys move
// through, shows what the picked or pointed-at week rests on, and goes on without
// the events when events.json fails.

import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, test } from "vitest";
import { installDom } from "./fakedom.js";

installDom();
const { seasonSection } = await import("../src/ui/season.js");
const { createNumbers } = await import("../src/numbers.js");
const { DEFAULT } = await import("../src/state.js");
const { en } = await import("../src/strings.js");
const { h } = await import("../src/ui/dom.js");

// the golden cases' history and events: weekly launches 2022 to 2026, Next Fests and Winter Sales
const { inputs } = JSON.parse(readFileSync(new URL("./golden/season.json", import.meta.url), "utf-8"));
const META = { snapshot_date: "2026-10-14", tags: [], languages: ["english"] };
// events.json has end dates; the golden events need only starts
const EVENTS = inputs.events.map((e) => ({
  ...e,
  end: new Date(Date.parse(e.start) + 7 * 86400000).toISOString().slice(0, 10),
}));

let body;
let intro;
let section;
let numbers;
function start() {
  body = h("div");
  intro = h("p");
  section = seasonSection(en, body, intro);
  numbers = createNumbers([], inputs.history, META.snapshot_date);
  section.start(numbers, META);
  section.draw({ ...DEFAULT, languages: [] });
}
const options = () => body.querySelectorAll(".ol-week");
const picked = () => options().findIndex((o) => o.getAttribute("aria-selected") === "true");
const key = (k) => document.activeElement.dispatch("keydown", { key: k });

describe("before events.json", () => {
  test("draws nothing and says it computes nothing yet", () => {
    start();
    expect(body.querySelector(".ol-week")).toBeNull();
    expect(section.pending({ ...DEFAULT, languages: [] })).toBe(false);
  });
});

describe("the weeks", () => {
  beforeEach(() => {
    start();
    section.setEvents(EVENTS);
  });

  test("are 26 options in one listbox, this week picked and the only tab stop", () => {
    expect(body.querySelectorAll('[role="listbox"]')).toHaveLength(1);
    expect(options()).toHaveLength(26);
    expect(picked()).toBe(0);
    expect(options().filter((o) => o.getAttribute("tabindex") === "0")).toHaveLength(1);
    expect(options()[0].getAttribute("aria-label")).toMatch(/^Week of Oct 12 to Oct 18: usually \d\.\d\d, /);
    expect(body.querySelector(".ol-good").textContent).toBe("Quiet is not the same as good.");
  });

  test("move with the arrow keys, Home and End", () => {
    options()[0].focus();
    key("ArrowRight");
    key("ArrowDown");
    expect(picked()).toBe(2);
    expect(document.activeElement).toBe(options()[2]);
    key("ArrowLeft");
    expect(picked()).toBe(1);
    key("End");
    expect(picked()).toBe(25);
    key("ArrowRight");
    expect(picked()).toBe(25);
    key("Home");
    expect(picked()).toBe(0);
    expect(options().filter((o) => o.getAttribute("tabindex") === "0")).toHaveLength(1);
  });

  test("say what the picked week rests on, and what a pointed-at week rests on", () => {
    // the week after Next Fest October 2026 (Oct 19): the golden history is busier then
    options()[2].click();
    const text = body.querySelector(".ol-detail").textContent;
    expect(text).toMatch(/^Week of Oct 26 to Nov 1: usually /);
    expect(text).toContain("1 week after Next Fest October");
    options()[10].dispatch("mouseenter");
    expect(body.querySelector(".ol-detail").textContent).toMatch(/^Week of Dec 21 to Dec 27/);
    body.querySelector(".ol").dispatch("mouseleave");
    expect(body.querySelector(".ol-detail").textContent).toMatch(/^Week of Oct 26 to Nov 1/);
  });

  test("keep the picked week when paid / free changes", () => {
    options()[3].click();
    section.draw({ ...DEFAULT, languages: [], group: "free" });
    expect(picked()).toBe(3);
    expect(intro.textContent).toBe(
      "How busy each coming week usually is, from past years' launches of free games in any language.",
    );
    section.draw({ ...DEFAULT, languages: ["english", "schinese"] });
    expect(intro.textContent).toBe(
      "How busy each coming week usually is, from past years' launches of paid games in English or Simplified Chinese.",
    );
  });

  test("are cached per languages, so a tag pick costs nothing", () => {
    expect(section.pending({ ...DEFAULT, languages: [], tags: [5] })).toBe(false);
    expect(section.pending({ ...DEFAULT, languages: ["schinese"] })).toBe(true);
  });

  test("show the events lanes under the weeks", () => {
    expect(body.querySelector(".hm-band-label").textContent).toBe("Events");
    expect(body.querySelectorAll(".hm-block-name").map((e) => e.textContent)).toContain("Next Fest October");
  });
});

test("without events.json, draws the calendar pattern and says the events are left out", () => {
  start();
  section.setEvents(null);
  expect(options()).toHaveLength(26);
  expect(body.querySelector(".ol-note").textContent).toBe(en.season.eventsFailed);
  expect(body.querySelector(".hm-band-label")).toBeNull();
  expect(body.textContent).not.toMatch(/false|null|undefined/);
});
