// The text and fill pairs Competition ahead uses pass WCAG's 4.5:1 in both themes.
// Which text goes on which fill is read from styles.css itself (the .sN rules, the
// far weeks, the event kinds), so a changed rule is checked too.

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

// the custom properties declared in the first block that starts with `selector`
function block(selector) {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`no ${selector} in styles.css`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
}

const light = block(":root {");
const dark = { ...light, ...block(':root[data-theme="dark"] {') };
const darkSystem = block(':root:not([data-theme="light"]) {');

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
// a token's colour as [r, g, b]: a hex, var(--x), or color-mix(in srgb, A p%, B)
function rgb(value, theme) {
  value = value.replace(/\/\*.*?\*\//g, "").trim();
  const v = value.match(/^var\((--[\w-]+)\)$/);
  if (v) return rgb(theme[v[1]], theme);
  if (/^#[0-9a-f]{6}$/i.test(value)) return hex(value);
  const m = value.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
  if (m) {
    const [a, p, b] = [rgb(m[1], theme), +m[2] / 100, rgb(m[3], theme)];
    return a.map((x, i) => x * p + b[i] * (1 - p));
  }
  throw new Error(`cannot read colour ${value}`);
}

const lin = (v) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
function contrast(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

// [fill, text] token pairs from rules like `.s4 { --fill: var(--heat-4); --on: var(--paper); }`
function stepPairs(prefix) {
  const rule = new RegExp(`^${prefix}\\.s(\\d) \\{ --fill: var\\((--[\\w-]+)\\); --on: var\\((--[\\w-]+)\\);`, "gm");
  return [...css.matchAll(rule)].map((m) => [`${prefix.replace(/\\/g, "")}.s${m[1]}`, m[2], m[3]]);
}
const steps = stepPairs("");
const far = stepPairs("\\.is-far ");

// the event kinds' fills (`.is-seasonal_sale { --fill: var(--heat-3); }`), all with ink text
const kinds = [...css.matchAll(/^\.is-(\w+) \{ --fill: var\((--[\w-]+)\); \}/gm)].map((m) => [`.is-${m[1]}`, m[2], "--ink"]);

const pairs = [
  ...steps,
  ...far,
  ...kinds,
  ["labels, notes and the game list", "--paper", "--ink-2"],
  ['"This week" and the current date', "--paper", "--accent-ui"],
  ["the year part's number (on paper)", "--paper", "--ink"],
  ["the phone summary, its section links, and a cell's tooltip", "--ink", "--paper"],
  // the outlook under 1024px: the picked or hovered week on the tint, its events as tags on the tint
  ["the picked week and what it rests on", "--tint", "--ink-2"],
  ["the picked week's date and value", "--tint", "--ink"],
  ["the outlook's event tags", "--tint", "--ink"],
  ["this week's date when picked", "--tint", "--accent-ui"],
  // Trends: the readout and summary, the axis, quarter names and notes, the quarter under way
  ["the trends readout and summary", "--paper", "--ink"],
  ["the trends axis, quarter names and notes", "--paper", "--ink-2"],
  ['the quarter under way ("so far")', "--paper", "--accent-ui"],
];

// Trends: the bars are marks, not text, so they need 3:1 (WCAG 1.4.11) against
// paper and against the hover shade, which is ink at a few percent over paper
const hoverShare = css.match(/\.tr-q:hover \.tr-plot \{ background: color-mix\(in srgb, var\(--ink\) (\d+)%, transparent\); \}/);
const HOVER = `color-mix(in srgb, var(--ink) ${hoverShare?.[1]}%, var(--paper))`;
const marks = [
  ["a quarter's bar and the hatching of the quarter under way", "var(--paper)", "var(--ink-2)"],
  ["the picked quarter's bar", "var(--paper)", "var(--accent-ui)"],
  ["a bar under the pointer", HOVER, "var(--ink-2)"],
  ["the picked bar under the pointer", HOVER, "var(--accent-ui)"],
];

test("the trends hover shade was found", () => {
  expect(hoverShare).not.toBeNull();
});

test("the trend bars keep system colours in forced colours (Windows high contrast drops backgrounds)", () => {
  const forced = css.slice(css.indexOf("@media (forced-colors: active)"));
  expect(forced).toMatch(/\.tr-bar \{ forced-color-adjust: none; background: CanvasText; \}/);
  expect(forced).toMatch(/\.tr-q\.is-picked \.tr-bar \{ background: Highlight; \}/);
});

test("the rules were found", () => {
  expect(steps).toHaveLength(8);
  expect(far).toHaveLength(7);
  expect(kinds.map(([k]) => k)).toEqual([".is-seasonal_sale", ".is-next_fest", ".is-themed_fest"]);
});

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_, t) => {
  test.each(pairs)("%s: %s with %s text is at least 4.5:1", (__, fill, text) => {
    expect(contrast(rgb(t[fill], t), rgb(t[text], t))).toBeGreaterThanOrEqual(4.5);
  });

  test.each(marks)("%s: at least 3:1", (__, fill, mark) => {
    expect(contrast(rgb(fill, t), rgb(mark, t))).toBeGreaterThanOrEqual(3);
  });

  test("the ramp runs from paper to ink without going back", () => {
    const c = Array.from({ length: 8 }, (__, i) => contrast(rgb(t[`--heat-${i}`], t), rgb(t["--paper"], t)));
    expect(t["--heat-0"]).toBe(t["--paper"]);
    for (let i = 1; i < 8; i++) expect(c[i]).toBeGreaterThan(c[i - 1]);
  });
});

test("the system dark theme and the picked dark theme use the same colours", () => {
  const plain = (v) => v.replace(/\/\*.*?\*\//g, "").trim();
  for (const [k, v] of Object.entries(darkSystem)) expect(plain(dark[k]), k).toBe(plain(v));
});
