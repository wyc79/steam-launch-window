import { describe, expect, test, vi } from "vitest";
import { createState, DEFAULT, query } from "../src/state.js";

describe("selection state", () => {
  test("starts with no tags, all of these, English, paid games and the relative measure", () => {
    expect(createState().get()).toEqual({
      tags: [],
      mode: "and",
      languages: ["english"],
      group: "paid",
      measure: "relative",
    });
    expect(DEFAULT).toEqual(createState().get());
  });

  test("a subscriber hears the state at once and after each change", () => {
    const state = createState();
    const fn = vi.fn();
    state.subscribe(fn);
    state.set({ mode: "or" });
    expect(fn.mock.calls.map(([s]) => s.mode)).toEqual(["and", "or"]);
  });

  test("setting the same values tells nobody", () => {
    const state = createState({ tags: [19, 1663] });
    const fn = vi.fn();
    state.subscribe(fn);
    state.set({ mode: "and", tags: [19, 1663] });
    state.addTag(19);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test("unsubscribing stops the calls", () => {
    const state = createState();
    const fn = vi.fn();
    const stop = state.subscribe(fn);
    stop();
    state.set({ group: "free" });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test("tags are added once, in order, and removed by id or from the end", () => {
    const state = createState();
    state.addTag(19);
    state.addTag(1663);
    state.addTag(19);
    expect(state.get().tags).toEqual([19, 1663]);
    state.addTag(3859);
    state.removeTag(1663);
    expect(state.get().tags).toEqual([19, 3859]);
    state.removeLastTag();
    expect(state.get().tags).toEqual([19]);
    state.removeLastTag();
    state.removeLastTag(); // nothing left: no error
    expect(state.get().tags).toEqual([]);
  });

  test("languages toggle on and off, and may all be off (any language)", () => {
    const state = createState();
    state.toggleLanguage("schinese");
    expect(state.get().languages).toEqual(["english", "schinese"]);
    state.toggleLanguage("english");
    state.toggleLanguage("schinese");
    expect(state.get().languages).toEqual([]);
  });

  test("the state cannot be changed behind the subscribers' backs", () => {
    const state = createState();
    expect(Object.isFrozen(state.get())).toBe(true);
    const before = state.get();
    state.addTag(19);
    expect(before.tags).toEqual([]);
  });

  test("an unknown mode, group or measure is an error and changes nothing", () => {
    const state = createState();
    expect(() => state.set({ mode: "xor" })).toThrow();
    expect(() => state.set({ group: "both" })).toThrow();
    expect(() => state.set({ measure: "ratio" })).toThrow();
    expect(state.get()).toEqual(DEFAULT);
  });

  test("query gives what the reference numbers take", () => {
    expect(query({ tags: [19], mode: "or", languages: ["english"], group: "free" })).toEqual({
      selection: [19],
      mode: "or",
      languages: ["english"],
    });
  });
});
