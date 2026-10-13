// The heatmap's text and fill pairs in styles.css pass WCAG's 4.5:1 in both themes.

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

// custom properties set to a hex colour in the first block that starts with `selector`
function tokens(selector) {
  const start = css.indexOf(selector);
  const block = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b/g)].map((m) => [m[1], m[2]]));
}

const light = tokens(":root {");
const dark = { ...light, ...tokens(':root[data-theme="dark"] {') };
const darkSystem = tokens(':root:not([data-theme="light"]) {');

const lin = (v) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};
function contrast(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

// text token on fill token, as the .sN and .is-far .sN rules pair them
function pairs() {
  const out = [];
  for (let i = 0; i < 8; i++) out.push([`--heat-${i}`, i < 4 ? "--ink" : "--paper"]);
  for (let i = 1; i < 8; i++) out.push([`--heat-far-${i}`, "--ink"]);
  out.push(["--paper", "--ink-2"]); // labels, notes, the game list
  return out;
}

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_, t) => {
  test.each(pairs())("%s with %s text is at least 4.5:1", (fill, text) => {
    expect(t[fill], fill).toBeDefined();
    expect(contrast(t[fill], t[text])).toBeGreaterThanOrEqual(4.5);
  });

  test("the ramp runs from paper to ink without going back", () => {
    const steps = Array.from({ length: 8 }, (_, i) => contrast(t[`--heat-${i}`], t["--paper"]));
    expect(t["--heat-0"]).toBe(t["--paper"]);
    for (let i = 1; i < 8; i++) expect(steps[i]).toBeGreaterThan(steps[i - 1]);
  });
});

test("the system dark theme and the picked dark theme use the same ramp", () => {
  for (const [k, v] of Object.entries(darkSystem)) if (k.startsWith("--heat")) expect(dark[k], k).toBe(v);
});
