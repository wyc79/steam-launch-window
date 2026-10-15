import { expect, test } from "vitest";

import methodsHtml from "virtual:methods-content";
import { methodsPage, syncTableTabStops } from "../src/methods.js";
import { h } from "../src/ui/dom.js";
import { HOME, REPO, masthead } from "../src/ui/masthead.js";
import { en, zh } from "../src/strings.js";
import { installDom } from "./fakedom.js";


test("the build-time article has its contents, sources, anchors, and language table", () => {
  expect(methodsHtml).toContain('<h1 id="methods">Methods</h1>');
  expect(methodsHtml).toContain('<a href="#trends">Trends</a>');
  expect(methodsHtml).toContain('<h2 id="what-history-says">What history says</h2>');
  expect(methodsHtml).toContain('<h2 id="competition-ahead">Competition ahead</h2>');
  expect(methodsHtml).toContain('<h3 id="most-anticipated">Most anticipated</h3>');
  expect(methodsHtml).toContain('<a href="#the-placebo-and-weekly-competition">');
  expect(methodsHtml).toContain('<h2 id="typical-for-this-time-of-year">Typical for this time of year</h2>');
  expect(methodsHtml).toContain('href="https://games-popularity.com/" target="_blank" rel="noopener"');
  expect(methodsHtml).toContain('href="https://huggingface.co/datasets/strikeoo/steam-launch-data"');
  expect(methodsHtml).toContain("With Simplified Chinese");
  expect(methodsHtml).toContain("55.0%");
  expect(methodsHtml).toContain("10 launches whose week begins before the analysis window");
  expect(methodsHtml).toContain("72 paid games without a usable price");
  expect(methodsHtml).toContain("625 launches, including 555 paid and 70 free launches");
  expect(methodsHtml).not.toContain("currently cover 626 launches");
});

test("the build-time Chinese article has translated content and the same section anchors", async () => {
  const article = await import("virtual:methods-content-zh").catch(() => null);
  expect(article).not.toBeNull();
  expect(article.default).toContain('<h1 id="methods">方法说明</h1>');
  expect(article.default).toContain('<h2 id="trends">趋势</h2>');
  expect(article.default).toContain('<h2 id="what-history-says">历史表现</h2>');
  expect(article.default).toContain('<h2 id="competition-ahead">未来竞争</h2>');
  expect(article.default).toContain('<h2 id="typical-for-this-time-of-year">一年中这个时段通常有多拥挤</h2>');
  expect(article.default).toContain("支持简体中文");
  expect(article.default).toContain("55.0%");
  expect(article.default).toContain('aria-label="付费游戏：发售条件"');
  expect(article.default).toContain("（在新标签页中打开）");
  for (const tag of ["Free to Play", "Strategy", "Roguelike", "Beat 'em up", "Horror", "Cozy", "Pixel Graphics", "Indie"]) {
    expect(article.default).toContain(tag);
  }
  expect(article.default).not.toContain(" (opens in a new tab)");
});


test("the Methods page uses the shared shell and has an article and back link", () => {
  const doc = installDom();
  doc.documentElement = doc.createElement("html");
  const page = methodsPage(en, methodsHtml);
  doc.body.append(...page);

  const article = doc.body.querySelector("article.methods");
  expect(article.innerHTML).toBe(methodsHtml);
  expect(doc.body.querySelector('.methods-back a').getAttribute("href")).toBe(import.meta.env.BASE_URL);
  expect(en.pageTitle(en.methods.title, en.title)).toContain("Methods");
});

test("the masthead opens GitHub in a new tab; the links home and within this site stay", () => {
  const doc = installDom();
  doc.documentElement = doc.createElement("html");
  doc.body.append(masthead(en, "methods"));

  const links = doc.body.querySelectorAll("a");
  expect(links.map((a) => [a.getAttribute("href"), a.getAttribute("target"), a.getAttribute("rel")])).toEqual([
    [HOME, null, null],
    [import.meta.env.BASE_URL, null, null],
    [`${import.meta.env.BASE_URL}methods.html`, null, null],
    [REPO, "_blank", "noopener"],
  ]);
  expect(links[3].textContent).toBe(`${en.mast.source}${en.newTab}`);
  expect(links[3].querySelector(".visually-hidden").textContent).toBe(en.newTab);
});

test("the masthead offers the bilingual switch and requests the other language", () => {
  const doc = installDom();
  doc.documentElement = doc.createElement("html");
  const changes = [];
  doc.body.append(masthead(zh, "methods", (language) => changes.push(language)));

  const toggle = doc.body.querySelector(".mast-language");
  expect(toggle.getAttribute("aria-label")).toBe("切换语言");
  expect(toggle.textContent).toBe("EN/中文");
  expect(toggle.querySelector('[data-opt="zh"]')).not.toBeNull();
  toggle.click();
  expect(changes).toEqual(["en"]);
});


test("every table frame is a named region, and a tab stop only while it scrolls", () => {
  const frames = methodsHtml.match(/<div class="method-table"[^>]*>/g);
  expect(frames).toEqual([
    '<div class="method-table" role="region" aria-label="Paid games: Launch condition" tabindex="0">',
    '<div class="method-table" role="region" aria-label="Reviews by language: With Simplified Chinese" tabindex="0">',
    '<div class="method-table" role="region" aria-label="Reviews by language: Without Simplified Chinese" tabindex="0">',
  ]);

  installDom();
  const wide = h("div", { class: "method-table", tabindex: "0" });
  const fits = h("div", { class: "method-table", tabindex: "0" });
  Object.assign(wide, { scrollWidth: 608, clientWidth: 328 });
  Object.assign(fits, { scrollWidth: 328, clientWidth: 328 });
  const root = h("div", {}, wide, fits);
  syncTableTabStops(root);
  expect([wide.getAttribute("tabindex"), fits.getAttribute("tabindex")]).toEqual(["0", null]);
  // wider again (a rotated phone, larger text): the stop comes back
  fits.scrollWidth = 400;
  syncTableTabStops(root);
  expect(fits.getAttribute("tabindex")).toBe("0");
});
