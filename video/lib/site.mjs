// Opening the live site the same way for the video and the cover.

import { VIEWPORT } from "../config.mjs";

// A browser context for the site: Chinese (the site's own language setting), light
// theme, and Google Analytics blocked so these runs do not count as visits.
export async function siteContext(browser, scale) {
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: scale,
    locale: "zh-CN",
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  await context.addInitScript(() => {
    if (location.hostname.endsWith("github.io")) localStorage.setItem("yc-lang", "zh");
  });
  await context.route(/googletagmanager\.com|google-analytics\.com|\/analytics\.js(\?|$)/, (route) => route.abort());
  return context;
}

// every section has drawn (none is aria-busy), the competition table has cells,
// and, after a tag is picked, its row is in the table
export async function waitSettled(page, expect = null) {
  await page.waitForFunction(
    (expect) =>
      !document.querySelector("main [aria-busy]") &&
      document.querySelectorAll("#ahead .hm-cell").length > 0 &&
      (!expect || document.querySelector("#ahead").innerText.includes(expect)),
    expect,
    { timeout: 60_000 },
  );
  await page.evaluate(() => document.fonts.ready);
}

// what typing `tag.type` offers first must be `tag.pick`, or the site has changed
export async function checkOffer(page, tag) {
  const first = await page.locator("li.tag-option").first().innerText();
  if (!first.startsWith(tag.pick)) throw new Error(`typing "${tag.type}" offers "${first}" first, not "${tag.pick}"`);
}
