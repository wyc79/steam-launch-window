import { expect, test } from "vitest";
import { en } from "../src/strings.js";
import { REPO } from "../src/ui/masthead.js";
import { SECTIONS, footer, sectionNumber, sections } from "../src/ui/sections.js";
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
    expect(link.textContent).toBe(`How this is measured: ${en.sections[key].title}`);
    expect(link.querySelector(".visually-hidden").textContent).toBe(`: ${en.sections[key].title}`);
    expect(link.getAttribute("href")).toBe(`${import.meta.env.BASE_URL}methods.html${anchors[key]}`);
  }
});

test("the footer's links off this site open in a new tab and say so; the Methods link stays", () => {
  installDom();
  const links = footer(en).el.querySelectorAll("a");
  expect(links.map((a) => [a.getAttribute("href"), a.getAttribute("target"), a.getAttribute("rel")])).toEqual([
    ["https://store.steampowered.com/", "_blank", "noopener"],
    ["https://games-popularity.com/", "_blank", "noopener"],
    ["https://huggingface.co/datasets/strikeoo/steam-launch-data", "_blank", "noopener"],
    [`${import.meta.env.BASE_URL}methods.html`, null, null],
    [REPO, "_blank", "noopener"],
  ]);
  for (const a of links.filter((a) => a.getAttribute("target"))) {
    expect(a.querySelector(".visually-hidden").textContent).toBe(en.newTab);
  }
  expect(links[3].querySelector(".visually-hidden")).toBeNull();
});
