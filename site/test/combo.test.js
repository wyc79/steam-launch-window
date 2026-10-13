import { describe, expect, test } from "vitest";
import { arrowActive, openActive } from "../src/combo.js";

describe("tag list highlight", () => {
  test("opening highlights the first option only when something is typed", () => {
    expect(openActive(true, 5)).toBe(0);
    expect(openActive(false, 5)).toBe(-1);
    expect(openActive(true, 0)).toBe(-1);
  });

  test("ArrowDown on a closed list with text only opens it, on the first option", () => {
    // type "rogue", Escape, ArrowDown: Roguelite (first), not the second option
    expect(arrowActive({ open: false, active: -1, typed: true, count: 3 }, 1)).toBe(0);
    expect(arrowActive({ open: false, active: -1, typed: true, count: 3 }, -1)).toBe(0);
  });

  test("on a closed, empty field the arrows open the list at the top or the bottom", () => {
    expect(arrowActive({ open: false, active: -1, typed: false, count: 8 }, 1)).toBe(0);
    expect(arrowActive({ open: false, active: -1, typed: false, count: 8 }, -1)).toBe(7);
  });

  test("on an open list the arrows move and wrap around", () => {
    expect(arrowActive({ open: true, active: 0, typed: true, count: 3 }, 1)).toBe(1);
    expect(arrowActive({ open: true, active: 2, typed: true, count: 3 }, 1)).toBe(0);
    expect(arrowActive({ open: true, active: 0, typed: true, count: 3 }, -1)).toBe(2);
    expect(arrowActive({ open: true, active: -1, typed: false, count: 3 }, -1)).toBe(2);
  });

  test("no options, no highlight", () => {
    expect(arrowActive({ open: true, active: -1, typed: true, count: 0 }, 1)).toBe(-1);
    expect(arrowActive({ open: false, active: -1, typed: true, count: 0 }, 1)).toBe(-1);
  });
});
