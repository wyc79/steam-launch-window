// The history panel as text: percentiles first, the meaning of quiet and busy in
// one line, and one line when the panel cannot show.

import { describe, expect, test } from "vitest";
import { historyPanel } from "../src/lib/heatmap.js";
import { formatBusy, panelView } from "../src/panelview.js";

const part = (games, busy_min, busy_max, median, p75, p90) => ({ games, busy_min, busy_max, median, p75, p90 });
const PANEL = {
  measure: "relative",
  paid: {
    games: 3950,
    shown: true,
    parts: {
      quiet: part(1300, 0, 0.62, 3, 14.5, 77.2),
      normal: part(1320, 0.63, 1.1, 3, 17, 93),
      busy: part(1330, 1.11, 3.5, 4, 18, 1020.4),
    },
  },
  free: { games: 40, shown: false, parts: { quiet: { games: 20 }, normal: { games: 12 }, busy: { games: 8 } } },
};

describe("a shown panel", () => {
  const v = panelView(PANEL, "paid", undefined, { tags: [1] });

  test("leads with the 75th and 90th percentiles, then the median and the launches", () => {
    expect(v.rows.map((r) => [r.name, r.range, r.p75, r.p90, r.median, r.games])).toEqual([
      ["Quiet", "0.00 to 0.62", "15", "77", "3", "1,300"],
      ["Normal", "0.63 to 1.10", "17", "93", "3", "1,320"],
      ["Busy", "1.11 to 3.50", "18", "1,020", "4", "1,330"],
    ]);
  });

  test("says what quiet and busy mean in one line, with the cut points", () => {
    expect(v.cuts).toBe(
      "Busy: other launches like yours that week, against the average week in the 13 weeks before. Quiet is up to 0.62 times that, busy over 1.10.",
    );
    expect(v.intro).toBe("Paid games like yours: 3,950 past launches with a 30-day review count.");
    expect(panelView(PANEL, "paid").intro).toBe("All paid games: 3,950 past launches with a 30-day review count.");
  });

  test("scales the bars by the largest 90th percentile", () => {
    expect(v.rows[2].bars.p90).toBe(1);
    expect(v.rows[0].bars.p75).toBeCloseTo(14.5 / 1020.4, 10);
  });

  test("raw counts say other launches, whole numbers", () => {
    const raw = { ...PANEL, measure: "raw", paid: { ...PANEL.paid, parts: { ...PANEL.paid.parts } } };
    raw.paid.parts.quiet = part(1300, 0, 12, 3, 14, 77);
    raw.paid.parts.normal = part(1320, 13, 25, 3, 17, 93);
    raw.paid.parts.busy = part(1330, 26, 26, 4, 18, 102);
    const r = panelView(raw, "paid");
    expect(r.cuts).toBe("Busy: how many other launches like yours that week. Quiet is up to 12, busy over 25.");
    expect(r.rows.map((x) => x.range)).toEqual(["0 to 12", "13 to 25", "26"]);
  });
});

describe("a hidden panel", () => {
  test("says so in one line and suggests fewer tags or Any of these", () => {
    expect(panelView(PANEL, "free")).toEqual({
      shown: false,
      text: "Too few past launches to split into quiet, normal and busy weeks (each needs 30). Try fewer tags or Any of these.",
    });
  });

  test("with no matching launches says that instead", () => {
    const v = panelView(historyPanel([], { selection: [1] }), "paid");
    expect(v.text).toBe("No past launches match. Try fewer tags or Any of these.");
  });
});

test("busy values: two decimals, or whole launches", () => {
  expect(formatBusy(1.1, "relative")).toBe("1.10");
  expect(formatBusy(1204, "raw")).toBe("1,204");
});
