// The video cover: the site's competition table for the video's tags, screenshotted
// live, under the title. Writes out/cover.png (16:9, 1920x1080) and out/cover-4x3.png
// (1440x1080, for platforms that ask for both).
//
//   node cover.mjs

import { mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { COVER, SITE_URL, TAGS } from "./config.mjs";
import { checkOffer, siteContext, waitSettled } from "./lib/site.mjs";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const OUT = here("out/");
const SIZES = { "cover.png": { width: 1920, height: 1080 }, "cover-4x3.png": { width: 1440, height: 1080 } };

const escape = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;");

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
try {
  // the table, at twice the size it is shown, for sharp edges and text
  const context = await siteContext(browser, 2);
  const site = await context.newPage();
  await site.goto(SITE_URL, { waitUntil: "networkidle" });
  await waitSettled(site);
  const input = site.locator("input.tag-input");
  for (const tag of TAGS) {
    await input.fill(tag.type);
    await checkOffer(site, tag);
    await site.keyboard.press("Enter");
    await waitSettled(site, tag.pick);
  }
  await input.blur();
  const table = await site.locator("#ahead .hm-wrap").screenshot({ animations: "disabled" });
  await context.close();

  let html = await readFile(here("cover.html"), "utf8");
  const fields = {
    site: SITE_URL,
    kicker: escape(COVER.kicker),
    title: COVER.title.map(escape).join("<br>"),
    line: escape(COVER.line),
    table: `data:image/png;base64,${table.toString("base64")}`,
  };
  for (const [k, v] of Object.entries(fields)) html = html.replaceAll(`{{${k}}}`, v);

  const page = await browser.newPage();
  for (const [file, viewport] of Object.entries(SIZES)) {
    await page.setViewportSize(viewport);
    await page.setContent(html, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `${OUT}${file}` });
    console.log(`${OUT}${file}`);
  }
} finally {
  await browser.close();
}
