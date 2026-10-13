// The top bar's section links and its one raw counts toggle, in a small stand-in DOM.

import { expect, test } from "vitest";
import { installDom } from "./fakedom.js";

installDom();
const observers = [];
globalThis.IntersectionObserver = class {
  constructor(fn) {
    this.fn = fn;
    this.targets = [];
    observers.push(this);
  }
  observe(el) {
    this.targets.push(el);
  }
};
const { topbar } = await import("../src/ui/topbar.js");
const { createState } = await import("../src/state.js");
const { en } = await import("../src/strings.js");
const { h } = await import("../src/ui/dom.js");

test("links to the four sections in page order, in the bar and (numbers only) in the phone summary", () => {
  const bar = topbar(en, createState());
  const links = bar.el.querySelectorAll(".bar-nav a");
  expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
    ["01 History", "#history"],
    ["02 Ahead", "#ahead"],
    ["03 Season", "#season"],
    ["04 Trends", "#trends"],
  ]);
  const short = bar.summary.querySelectorAll(".summary-nav a");
  expect(short.map((a) => [a.textContent, a.getAttribute("aria-label")])).toEqual([
    ["01", "01 History"],
    ["02", "02 Ahead"],
    ["03", "03 Season"],
    ["04", "04 Trends"],
  ]);
});

test("the section in view is marked in both places", () => {
  const bar = topbar(en, createState());
  const els = ["history", "ahead", "season"].map((id) => {
    const el = h("section", { id });
    el.id = id;
    return el;
  });
  bar.watchSections(els);
  const watcher = observers.at(-1);
  watcher.fn([{ target: els[1], isIntersecting: true }]);
  const current = [...bar.el.querySelectorAll(".bar-nav a"), ...bar.summary.querySelectorAll(".summary-nav a")]
    .filter((a) => a.getAttribute("aria-current") === "location")
    .map((a) => a.getAttribute("href"));
  expect(current).toEqual(["#ahead", "#ahead"]);
});

test("one raw counts toggle sets the shared measure, and its hint names both sections", () => {
  const state = createState();
  const bar = topbar(en, state);
  const box = bar.el.querySelector(".raw-toggle input");
  box.checked = true;
  box.dispatch("change");
  expect(state.get().measure).toBe("raw");
  expect(bar.el.querySelector(".raw-toggle").getAttribute("title")).toBe(
    "Plain counts instead of a comparison with a usual week, in sections 01 and 02",
  );
  state.set({ measure: "relative" });
  expect(box.checked).toBe(false);
});
