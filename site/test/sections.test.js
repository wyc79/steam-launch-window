import { expect, test } from "vitest";
import { en } from "../src/strings.js";
import { SECTIONS, sectionNumber, sections } from "../src/ui/sections.js";
import { installDom } from "./fakedom.js";

test("the trends first, then history and the model, the heatmap and the season, numbered in that order", () => {
  expect(SECTIONS).toEqual(["trends", "history", "ahead", "season"]);
  expect(SECTIONS.map(sectionNumber)).toEqual(["01", "02", "03", "04"]);
  for (const key of SECTIONS) expect(en.sections[key].title).toBeTruthy();
});

test("the top bar's warning points at the history section's own number", () => {
  expect(en.bar.fewPast(sectionNumber("history"))).toBe("Too few for section 02.");
});

test("each section links to its stable Methods anchor", () => {
  installDom();
  const parts = sections(en);
  const anchors = {
    trends: "#trends",
    history: "#what-history-says",
    ahead: "#competition-ahead",
    season: "#typical-for-this-time-of-year",
  };

  for (const [index, key] of SECTIONS.entries()) {
    const link = parts.els[index].querySelector("a.method-link");
    expect(link.textContent).toBe("How this is measured");
    expect(link.getAttribute("href")).toBe(`${import.meta.env.BASE_URL}methods.html${anchors[key]}`);
  }
});
