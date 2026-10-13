// The JavaScript ports must give what the Python reference gives on the golden
// cases (written by `python -m analysis.golden`): strings, flags and nulls exactly,
// numbers within a tight tolerance, and without changing their inputs.

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { fromTable } from "../src/lib/data.js";
import { toDay, toIso, weekStart } from "../src/lib/dates.js";
import * as hm from "../src/lib/heatmap.js";
import * as season from "../src/lib/season.js";

const TOLERANCE = 1e-9;

// fn name in the golden files: how to call the port (the Python side is analysis/golden.py CALLS)
const CALLS = {
  matches: (a) => hm.matches(a.tags, a.selection, a.mode),
  speaks: (a) => hm.speaks(a.langs, a.languages),
  heatmap: (a) => hm.heatmap(a.games, a.today, a),
  heatmap_rows: (a) => hm.heatmapRows(a.games, a.today, a),
  match_count: (a) => hm.matchCount(a.games, a.history, a),
  normalized: (a) => hm.normalized(hm.heatmap(a.games, a.today, a)),
  niche_trend: (a) => hm.nicheTrend(a.games, a.history, a.today, a),
  week_games: (a) => hm.weekGames(a.games, a.today, a.week, a),
  percentile: (a) => hm.percentile(a.values, a.q),
  round2: (a) => hm.round2(a.x),
  cut_points: (a) => hm.cutPoints(a.busy),
  history_panel: (a) => hm.historyPanel(a.history, { ...a, minGroup: a.min_group }),
  weekly_ratios: (a) => season.weeklyRatios(a.history, a),
  event_series: (a) => season.eventSeries(a.events),
  estimate: (a) => season.estimate(a.week, a.ratios, a.series, a.before),
  outlook: (a) => season.outlook(a.history, a.events, a.today, a),
  table_rows: (a) => fromTable(a.table, a.meta),
};

// where `actual` differs from `expected`, as "path: actual vs expected" lines
function differences(actual, expected, path = "$") {
  if (typeof expected === "number") {
    if (typeof actual !== "number") return [`${path}: ${actual} vs ${expected}`];
    // JSON drops Python's int / float difference, so every number gets the tolerance
    const ok = Math.abs(actual - expected) <= TOLERANCE * Math.max(1, Math.abs(expected));
    return ok ? [] : [`${path}: ${actual} vs ${expected}`];
  }
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || actual.length !== expected.length) {
      return [`${path}: ${JSON.stringify(actual)} vs ${JSON.stringify(expected)}`];
    }
    return expected.flatMap((e, i) => differences(actual[i], e, `${path}[${i}]`));
  }
  if (expected !== null && typeof expected === "object") {
    if (actual === null || typeof actual !== "object" || Array.isArray(actual)) {
      return [`${path}: ${JSON.stringify(actual)} vs an object`];
    }
    const keys = Object.keys(expected).sort();
    const got = Object.keys(actual).sort();
    if (keys.join() !== got.join()) return [`${path}: keys ${got} vs ${keys}`];
    return keys.flatMap((k) => differences(actual[k], expected[k], `${path}.${k}`));
  }
  return actual === expected ? [] : [`${path}: ${JSON.stringify(actual)} vs ${JSON.stringify(expected)}`];
}

for (const file of ["heatmap", "panel", "season", "data"]) {
  const golden = JSON.parse(readFileSync(new URL(`./golden/${file}.json`, import.meta.url), "utf-8"));
  describe(file, () => {
    test.each(golden.cases.map((c) => [c.name, c]))("%s", (_, c) => {
      // "$name" stands for an input; a private copy, so that one case cannot change another's inputs
      const input = (v) => (typeof v === "string" && v.startsWith("$") ? golden.inputs[v.slice(1)] : v);
      const args = structuredClone(Object.fromEntries(Object.entries(c.args).map(([k, v]) => [k, input(v)])));
      const before = structuredClone(args);
      expect(differences(CALLS[c.fn](args), c.expected)).toEqual([]);
      expect(args).toEqual(before); // the ports must not change what they are given
    });
  });
}

test("an unknown mode or measure is an error, as in Python", () => {
  expect(() => hm.matches([1], [1], "xor")).toThrow();
  expect(() => hm.historyPanel([], { measure: "ratio" })).toThrow();
  expect(() => hm.percentile([], 0.5)).toThrow();
});

test("dates stay on their calendar day whatever the machine's time zone", () => {
  expect(weekStart("2026-12-31")).toBe("2026-12-28");
  expect(weekStart("2026-03-08")).toBe("2026-03-02"); // a US clock change
  expect(toIso(toDay("2024-02-29") + 1)).toBe("2024-03-01");
});
