// The user's selection, the one piece of state the sections share. The top bar
// changes it; every section subscribes and redraws from it.

import { GROUPS, MEASURES, MODES } from "./lib/heatmap.js";

// measure: how the history panel ranks weeks ("relative" by default, or "raw"
// counts); the match count's red uses the same one, so it lives here
export const DEFAULT = Object.freeze({
  tags: [],
  mode: "and",
  languages: ["english"],
  group: "paid",
  measure: "relative",
});

function same(a, b) {
  return Object.keys(a).every((k) =>
    Array.isArray(a[k]) ? a[k].length === b[k].length && a[k].every((x, i) => x === b[k][i]) : a[k] === b[k],
  );
}

function check(s) {
  if (!MODES.includes(s.mode)) throw new Error(`mode must be one of ${MODES}, not ${s.mode}`);
  if (!GROUPS.includes(s.group)) throw new Error(`group must be one of ${GROUPS}, not ${s.group}`);
  if (!MEASURES.includes(s.measure)) throw new Error(`measure must be one of ${MEASURES}, not ${s.measure}`);
  if (!Array.isArray(s.tags) || !Array.isArray(s.languages)) throw new Error("tags and languages must be lists");
}

export function createState(initial = DEFAULT) {
  let state = Object.freeze({ ...DEFAULT, ...initial });
  check(state);
  const subscribers = new Set();

  function set(patch) {
    const next = Object.freeze({ ...state, ...patch });
    check(next);
    if (same(next, state)) return;
    state = next;
    for (const fn of subscribers) fn(state);
  }

  return {
    get: () => state,
    set,
    // calls `fn` now and after every change; returns a function that stops it
    subscribe(fn) {
      subscribers.add(fn);
      fn(state);
      return () => subscribers.delete(fn);
    },
    addTag(id) {
      if (!state.tags.includes(id)) set({ tags: [...state.tags, id] });
    },
    removeTag: (id) => set({ tags: state.tags.filter((t) => t !== id) }),
    removeLastTag: () => set({ tags: state.tags.slice(0, -1) }),
    toggleLanguage: (code) =>
      set({
        languages: state.languages.includes(code)
          ? state.languages.filter((x) => x !== code)
          : [...state.languages, code],
      }),
  };
}

// what the reference numbers in lib/ take
export function query(s) {
  return { selection: s.tags, mode: s.mode, languages: s.languages };
}
