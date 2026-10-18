// Records the three clips (live site, Hugging Face dataset page, end card) into
// build/clips/ and writes build/timeline.json: each clip's length and when each
// subtitle shows. compose.mjs turns that into the final video.
//
//   node record.mjs            all clips
//   node record.mjs site       one clip (site | dataset | end | credits)

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { CREDITS, DATASET_URL, END_CARD, FPS, SCALE, SITE_URL, TAGS, VIEWPORT, WEEK } from "./config.mjs";
import { Clip } from "./lib/clip.mjs";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const BUILD = here("build/");
const CLIPS = here("build/clips/");

const top = (page, selector) =>
  page.evaluate((sel) => {
    const el = typeof sel === "string" ? document.querySelector(sel) : null;
    if (!el) throw new Error(`no element ${sel}`);
    return el.getBoundingClientRect().top + window.scrollY;
  }, selector);

// every section has drawn (none is aria-busy), the competition table has cells,
// and, after a tag is picked, its row is in the table
async function waitSettled(page, expect = null) {
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

async function recordSite(page) {
  await page.goto(SITE_URL, { waitUntil: "networkidle" });
  await waitSettled(page);
  await page.waitForTimeout(500);
  const bar = await page.evaluate(() => document.querySelector(".bar").getBoundingClientRect().height);
  const clip = new Clip(page, `${CLIPS}site.mp4`, FPS);

  // 1. the page as it opens
  await clip.hold(0.3);
  clip.start("intro");
  await clip.hold(3.9);
  clip.end();

  // 2. the next 13 weeks, all games, with Steam sales and Next Fest marked
  await clip.scrollTo((await top(page, "#ahead")) - bar - 24, 1.6);
  clip.start("calendar");
  await clip.hold(4.0);
  clip.end();

  // 3. narrow it to a niche: type two tags into the sticky bar
  clip.start("tags");
  const input = page.locator("input.tag-input");
  await input.focus();
  await clip.hold(0.4);
  for (const tag of TAGS) {
    // Latin letters key by key; Chinese arrives whole, as an input method commits it
    if (/^[\x20-\x7e]+$/.test(tag.type)) await clip.type(tag.type);
    else {
      await page.keyboard.insertText(tag.type);
      await clip.hold(0.2);
    }
    const first = await page.locator("li.tag-option").first().innerText();
    if (!first.startsWith(tag.pick)) throw new Error(`typing "${tag.type}" offers "${first}" first, not "${tag.pick}"`);
    await clip.hold(0.8);
    await page.keyboard.press("Enter");
    await waitSettled(page, tag.pick);
    await clip.hold(1.0);
  }
  await input.blur();
  await clip.hold(1.8);
  clip.end();

  // 4. open one week: the games launching in it, and the niche's most anticipated
  clip.start("week");
  // the bottom row's cell in that week's column (columns count from --wk:2, this week),
  // clicked in the DOM so no pointer rests on the table afterwards
  const before = await page.evaluate(() => window.scrollY);
  await page.evaluate((wk) => {
    const cells = [...document.querySelectorAll("#ahead .hm-cell")].filter(
      (el) => el.style.getPropertyValue("--wk").trim() === String(wk),
    );
    if (!cells.length) throw new Error(`no week column ${wk}`);
    cells.at(-1).click();
  }, WEEK + 2);
  await page.waitForSelector("#ahead .ah-detail-head");
  // focusing the cell nudges the page; undo that so the move below is one smooth scroll
  await page.evaluate((y) => window.scrollTo({ top: y, behavior: "instant" }), before);
  await clip.hold(1.2); // the cell's count box shows, as it does on a click
  await page.keyboard.press("Escape"); // the site's own way to close that box
  await clip.scrollTo((await top(page, "#ahead .ah-detail")) - bar - 20, 1.4);
  await clip.hold(3.6);
  clip.end();

  // 5. how similar past launches did
  await clip.scrollTo((await top(page, "#history")) - bar - 24, 1.8);
  clip.start("history");
  await clip.hold(4.4);
  clip.end();
  await clip.hold(0.3); // a beat after the subtitle, before the cut
  return clip.close();
}

async function recordDataset(page) {
  await page.goto(DATASET_URL, { waitUntil: "networkidle" });
  await page.waitForSelector("table tbody tr", { timeout: 60_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1000);
  const clip = new Clip(page, `${CLIPS}dataset.mp4`, FPS);
  await clip.hold(0.3);
  clip.start("dataset");
  await clip.hold(2.6);
  const configs = await page.evaluate(() => {
    const h = [...document.querySelectorAll("h1, h2, h3, h4")].find((e) => e.textContent.trim() === "What is here");
    return h ? h.getBoundingClientRect().top + window.scrollY : null;
  });
  if (configs === null) throw new Error('no "What is here" heading on the dataset card');
  await clip.scrollTo(configs - 40, 1.6);
  await clip.hold(2.8);
  clip.end();
  await clip.hold(0.7); // under the fade to the end card
  return clip.close();
}

// a still card from an HTML template in this folder, its {{fields}} filled in
async function recordCard(page, name, template, fields, seconds) {
  let html = await readFile(here(template), "utf8");
  for (const [k, v] of Object.entries({ ...fields, site: SITE_URL })) html = html.replaceAll(`{{${k}}}`, v);
  await page.setContent(html, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  const clip = new Clip(page, `${CLIPS}${name}.mp4`, FPS);
  await clip.hold(seconds);
  return clip.close();
}

const escape = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const recordEnd = (page) => recordCard(page, "end", "endcard.html", END_CARD, 4.2);
const recordCredits = (page) =>
  recordCard(page, "credits", "credits.html", {
    rows: CREDITS.map(([what, who]) => `<div class="row"><span class="what">${escape(what)}</span><span class="who">${escape(who)}</span></div>`).join(""),
  }, 3.4);

const RECORDERS = { site: recordSite, dataset: recordDataset, end: recordEnd, credits: recordCredits };

const only = process.argv[2];
if (only && !RECORDERS[only]) throw new Error(`unknown clip ${only}; one of ${Object.keys(RECORDERS)}`);
await mkdir(CLIPS, { recursive: true });

let timeline = { clips: {} };
try {
  timeline = JSON.parse(await readFile(`${BUILD}timeline.json`, "utf8"));
} catch {}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
    locale: "zh-CN",
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  // the site in Chinese (its language switch keeps the choice here)
  await context.addInitScript(() => {
    if (location.hostname.endsWith("github.io")) localStorage.setItem("yc-lang", "zh");
  });
  // keep recording runs out of the site's visitor statistics
  await context.route(/googletagmanager\.com|google-analytics\.com|\/analytics\.js(\?|$)/, (route) => route.abort());

  for (const [name, record] of Object.entries(RECORDERS)) {
    if (only && name !== only) continue;
    const page = await context.newPage();
    const started = Date.now();
    const result = await record(page);
    timeline.clips[name] = { ...result, file: `clips/${name}.mp4` };
    console.log(`${name}: ${result.seconds.toFixed(2)} s of video in ${((Date.now() - started) / 1000).toFixed(0)} s`);
    await page.close();
  }
} finally {
  await browser.close();
}
timeline.fps = FPS;
timeline.size = { width: Math.round(VIEWPORT.width * SCALE), height: Math.round(VIEWPORT.height * SCALE) };
timeline.recorded = new Date().toISOString();
await writeFile(`${BUILD}timeline.json`, JSON.stringify(timeline, null, 2));
