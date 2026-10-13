import { expect, test } from "vitest";
import { en } from "../src/strings.js";
import { SECTIONS, sectionNumber } from "../src/ui/sections.js";

test("history and the model come first, the heatmap last, numbered in that order", () => {
  expect(SECTIONS).toEqual(["history", "season", "ahead"]);
  expect(SECTIONS.map(sectionNumber)).toEqual(["01", "02", "03"]);
  for (const key of SECTIONS) expect(en.sections[key].title).toBeTruthy();
});

test("the top bar's warning points at the history section's own number", () => {
  expect(en.bar.fewPast(sectionNumber("history"))).toBe("Too few for section 01.");
});
