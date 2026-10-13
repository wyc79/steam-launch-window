// Trends, drawn into a small stand-in DOM (test/fakedom.js): 20 quarters as a
// listbox the arrow keys move through, a readout of the picked or pointed-at
// quarter, the view switch (share off with no tags), and a line instead of a
// chart when nothing matches.

import { beforeEach, describe, expect, test } from "vitest";
import { installDom } from "./fakedom.js";

installDom();
const { trendsSection } = await import("../src/ui/trends.js");
const { createNumbers } = await import("../src/numbers.js");
const { DEFAULT } = await import("../src/state.js");
const { en } = await import("../src/strings.js");
const { h } = await import("../src/ui/dom.js");

const past = (day, tags, free = false) => ({
  launch_date: day,
  launch_type: "full",
  tags,
  langs: ["english"],
  free,
  reviews_30d: null,
});
// every quarter of 2022 to 2026 so far: two launches, one with tag 1
const HISTORY = [];
for (let y = 2022; y <= 2026; y++) {
  for (const m of ["02", "05", "08", "11"]) {
    const day = y === 2026 && m === "11" ? "10-05" : `${m}-10`;
    HISTORY.push(past(`${y}-${day}`, [1]), past(`${y}-${day}`, [2]));
  }
}
HISTORY.push(past("2024-08-11", [1], true));

let body;
let section;
function start(st = { ...DEFAULT, tags: [1] }) {
  body = h("div");
  section = trendsSection(en, body);
  section.start(createNumbers([], HISTORY, "2026-10-13"));
  section.draw(st);
}
const options = () => body.querySelectorAll(".tr-q");
const picked = () => options().findIndex((o) => o.getAttribute("aria-selected") === "true");
const key = (k) => document.activeElement.dispatch("keydown", { key: k });
const radio = (v) => body.querySelectorAll("input").find((i) => i.getAttribute("value") === v);
const readout = () => body.querySelector(".tr-readout").textContent;

describe("the quarters", () => {
  beforeEach(() => start());

  test("are 20 options in one listbox, the last full quarter picked and the only tab stop", () => {
    expect(body.querySelectorAll('[role="listbox"]')).toHaveLength(1);
    expect(options()).toHaveLength(20);
    expect(picked()).toBe(18);
    expect(options().filter((o) => o.getAttribute("tabindex") === "0")).toHaveLength(1);
    expect(options()[18].getAttribute("aria-label")).toBe("2026 Q3: 1 of 2 paid launches (50.0%)");
    expect(readout()).toBe("2026 Q3: 1 of 2 paid launches (50.0%)");
  });

  test("the quarter under way is marked partial and says so far", () => {
    const last = options()[19];
    expect(last.classList.contains("is-partial")).toBe(true);
    expect(last.getAttribute("aria-label")).toMatch(/^2026 Q4 so far \(Oct 1 to Oct 12\): /);
    expect(last.querySelector(".tr-sofar").textContent).toBe("so far");
    expect(body.querySelector(".tr-notes").textContent).toContain("Hatched: 2026 Q4 is not over (12 of 92 days so far).");
    expect(body.querySelector(".tr-notes").textContent).toContain(en.trends.noForecast);
  });

  test("move with the arrow keys, Home and End", () => {
    options()[18].focus();
    key("ArrowLeft");
    key("ArrowUp");
    expect(picked()).toBe(16);
    expect(document.activeElement).toBe(options()[16]);
    key("End");
    expect(picked()).toBe(19);
    key("ArrowRight");
    expect(picked()).toBe(19);
    key("Home");
    expect(picked()).toBe(0);
    expect(readout()).toMatch(/^2022 Q1: /);
    expect(options().filter((o) => o.getAttribute("tabindex") === "0")).toHaveLength(1);
  });

  test("the readout follows the pointer and goes back to the picked quarter", () => {
    options()[3].dispatch("mouseenter");
    expect(readout()).toMatch(/^2022 Q4: /);
    body.querySelector(".tr").dispatch("mouseleave");
    expect(readout()).toMatch(/^2026 Q3: /);
  });

  test("keep the picked quarter when paid / free changes", () => {
    options()[10].click();
    section.draw({ ...DEFAULT, tags: [1], group: "free" });
    expect(picked()).toBe(10);
    expect(readout()).toBe("2024 Q3: 1 of 1 free launches (100.0%)");
  });

  test("the axis starts at 0 and the years run under the quarters", () => {
    expect(body.querySelectorAll(".tr-tick")[0].textContent).toBe("0%");
    expect(body.querySelectorAll(".tr-year").map((y) => y.textContent)).toEqual(["2022", "2023", "2024", "2025", "2026"]);
  });
});

describe("the view switch", () => {
  test("share by default; per quarter and cumulative on request", () => {
    start();
    expect(radio("share").checked).toBe(true);
    radio("cumulative").dispatch("change");
    expect(radio("cumulative").checked).toBe(true);
    expect(readout()).toBe("2026 Q3: 19 paid launches since 2022 (1 that quarter)");
    radio("count").dispatch("change");
    expect(body.querySelector(".tr-summary").textContent).toMatch(/^Paid launches in English with your tags: 1 a quarter/);
  });

  test("with no tags the share is off, and the counts show with one line saying why", () => {
    start({ ...DEFAULT });
    expect(radio("share").disabled).toBe(true);
    expect(radio("count").checked).toBe(true);
    expect(body.querySelector(".tr-fallback").textContent).toBe(en.trends.fallback);
    expect(readout()).toBe("2026 Q3: 2 paid launches");
    section.draw({ ...DEFAULT, tags: [1] }); // a tag picked: back to the share
    expect(radio("share").checked).toBe(true);
    expect(radio("share").disabled).toBe(false);
    expect(body.querySelector(".tr-fallback").textContent).toBe("");
  });
});

test("nothing matching: a line instead of the chart", () => {
  start({ ...DEFAULT, tags: [9] });
  expect(options()).toHaveLength(0);
  expect(body.querySelector(".tr-empty").textContent).toBe(en.trends.empty);
  section.draw({ ...DEFAULT, tags: [1] });
  expect(options()).toHaveLength(20);
  expect(body.textContent).not.toMatch(/false|null|undefined|NaN/);
});
