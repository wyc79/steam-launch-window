import { expect, test } from "vitest";

import methodsHtml from "virtual:methods-content";
import { methodsPage, syncTableTabStops } from "../src/methods.js";
import { h } from "../src/ui/dom.js";
import { en } from "../src/strings.js";
import { installDom } from "./fakedom.js";


test("the build-time article has its contents, sources, anchors, and language table", () => {
  expect(methodsHtml).toContain('<h1 id="methods">Methods</h1>');
  expect(methodsHtml).toContain('<a href="#trends">Trends</a>');
  expect(methodsHtml).toContain('<h2 id="what-history-says">What history says</h2>');
  expect(methodsHtml).toContain('<h2 id="competition-ahead">Competition ahead</h2>');
  expect(methodsHtml).toContain('<h2 id="typical-for-this-time-of-year">Typical for this time of year</h2>');
  expect(methodsHtml).toContain('href="https://games-popularity.com/"');
  expect(methodsHtml).toContain('href="https://huggingface.co/datasets/strikeoo/steam-launch-data"');
  expect(methodsHtml).toContain("With Simplified Chinese");
  expect(methodsHtml).toContain("55.0%");
  expect(methodsHtml).toContain("10 launches whose week begins before the analysis window");
  expect(methodsHtml).toContain("72 paid games without a usable price");
  expect(methodsHtml).toContain("625 launches, including 555 paid and 70 free launches");
  expect(methodsHtml).not.toContain("currently cover 626 launches");
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
