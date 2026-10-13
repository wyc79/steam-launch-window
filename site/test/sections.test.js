import { expect, test } from "vitest";
import { en } from "../src/strings.js";
import { SECTIONS, sectionNumber } from "../src/ui/sections.js";

test("the trends first, then history and the model, the heatmap and the season, numbered in that order", () => {
  expect(SECTIONS).toEqual(["trends", "history", "ahead", "season"]);
  expect(SECTIONS.map(sectionNumber)).toEqual(["01", "02", "03", "04"]);
  for (const key of SECTIONS) expect(en.sections[key].title).toBeTruthy();
});

test("the top bar's warning points at the history section's own number", () => {
  expect(en.bar.fewPast(sectionNumber("history"))).toBe("Too few for section 02.");
});
