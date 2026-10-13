// What history says, drawn into a small stand-in DOM (test/fakedom.js): the panel
// for the selection, the raw counts toggle that sets the shared measure, and the
// model's lines (loading, missing, not ready, paid, free, Simplified Chinese).

import { beforeEach, describe, expect, test } from "vitest";
import { installDom } from "./fakedom.js";

installDom();
const { historySection } = await import("../src/ui/history.js");
const { createNumbers } = await import("../src/numbers.js");
const { createState, DEFAULT } = await import("../src/state.js");
const { en } = await import("../src/strings.js");
const { h } = await import("../src/ui/dom.js");

const DAY = 86400000;
// 100 weeks from 2024-01-01 with 1, 2, 3, 2 and 4 launches in turn: three parts of 30 or more
const HISTORY = [];
for (let i = 0; i < 100; i++) {
  for (let j = 0; j < [1, 2, 3, 2, 4][i % 5]; j++) {
    HISTORY.push({
      tags: [1],
      langs: ["english"],
      free: false,
      launch_type: "full",
      launch_date: new Date(Date.UTC(2024, 0, 1) + (i * 7 + j) * DAY).toISOString().slice(0, 10),
      reviews_30d: (i * 37 + j * 11) % 101,
    });
  }
}
const effect = (key, rate_ratio, low, high, extra = {}) => ({ key, rate_ratio, low, high, p: 0.001, ...extra });
const MODEL = {
  paid: {
    status: "ok",
    competition_measure: "comp_tier",
    reviews: { effects: [effect("sale", 0.6343, 0.5326, 0.7553), effect("comp_tier", 0.991, 0.9879, 0.9941)] },
    holidays: { with_schinese: { cn_national: effect("cn_national_schinese", 0.4783, 0.2424, 0.9439) } },
  },
  free: { status: "unreliable", caveats: ["not yet"] },
};

let body;
let selection;
let section;
function draw(patch = {}, model) {
  body = h("div");
  selection = createState({ ...DEFAULT, ...patch });
  section = historySection(en, body, selection);
  section.start(createNumbers([], HISTORY, "2026-10-13"));
  if (model !== undefined) section.setModel(model);
  selection.subscribe((st) => section.draw(st));
}

describe("the panel", () => {
  beforeEach(() => draw({ languages: [] }));

  test("shows the 75th and 90th percentiles first, then the median and the launches", () => {
    const heads = body.querySelectorAll(".hs-table thead th").map((th) => th.querySelector(".hs-long")?.textContent ?? th.textContent);
    expect(heads).toEqual(["Launch week", "75th percentile", "90th percentile", "Median", "Launches"]);
    const rows = body.querySelectorAll(".hs-table tbody tr");
    expect(rows.map((r) => r.querySelector(".hs-part").textContent)).toEqual(["Quiet", "Normal", "Busy"]);
    expect(rows[0].querySelectorAll("td")).toHaveLength(5); // four numbers and the bars
    expect(body.querySelector(".hs-cuts").textContent).toMatch(/^Busy: other launches like yours that week/);
  });

  test("raw counts set the shared measure, so the top bar's red follows", () => {
    const box = body.querySelector(".hs-raw input");
    expect(box.checked).toBe(false);
    box.checked = true;
    box.dispatch("change");
    expect(selection.get().measure).toBe("raw");
    expect(body.querySelector(".hs-cuts").textContent).toMatch(/^Busy: how many other launches like yours that week/);
    expect(body.querySelector(".hs-raw input").checked).toBe(true);
  });

  test("too few launches: one line that suggests fewer tags or Any of these", () => {
    selection.set({ tags: [2] });
    expect(body.querySelector(".hs-table")).toBeNull();
    expect(body.querySelector(".hs-few").textContent).toBe("No past launches match. Try fewer tags or Any of these.");
    selection.set({ tags: [], group: "free" }); // no free launches in the history
    expect(body.querySelector(".hs-few").textContent).toBe("No past launches match. Try fewer tags or Any of these.");
  });
});

describe("the model's lines", () => {
  test("say loading until model.json is in, then not ready when it is missing", () => {
    draw();
    expect(body.querySelector(".hs-timing").textContent).toBe(en.bar.loading);
    section.setModel(null);
    expect(body.querySelector(".hs-timing").textContent).toBe("Not ready yet.");
  });

  test("show the paid lines and the caveat", () => {
    draw({}, MODEL);
    const lines = body.querySelectorAll(".hs-timing .hs-lines li").map((li) => li.textContent);
    expect(lines[0]).toBe("Avoid launching during a Steam seasonal sale: such launches got 37% fewer reviews (24% to 47% fewer).");
    expect(body.querySelector(".hs-caveat").textContent).toBe(en.history.caveat);
    expect(body.querySelector(".hs-china")).toBeNull();
    expect(body.textContent).not.toMatch(/false|null|undefined/);
  });

  test("a group that is not ok shows one line and none of its numbers", () => {
    draw({ group: "free" }, MODEL);
    expect(body.querySelector(".hs-timing").textContent).toBe("Not ready yet.");
  });

  test("China's holidays with Simplified Chinese picked", () => {
    draw({ languages: ["english", "schinese"] }, MODEL);
    expect(body.querySelector(".hs-china").textContent).toBe(
      `${en.history.china}National Day: 52% fewer reviews (6% to 76% fewer).`,
    );
  });
});
