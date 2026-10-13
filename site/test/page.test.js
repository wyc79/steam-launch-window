import { describe, expect, test, vi } from "vitest";
import { connect } from "../src/page.js";
import { createState } from "../src/state.js";
import { en } from "../src/strings.js";

const GAMES = [{ tags: [1], langs: ["english"], free: false }];
const HISTORY = [{ tags: [1], langs: ["english"], free: false, launch_type: "full", launch_date: "2024-01-01", reviews_30d: 3 }];
const META = { snapshot_date: "2026-10-13", tags: [[1, "Action", 1, 1]], languages: ["english"] };

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)));
  promise.catch(() => {});
  return { promise, resolve, reject };
}

// loadData's shape, each file resolved or failed by the test
function fakeData() {
  const files = Object.fromEntries(["meta", "upcoming", "history", "events", "model"].map((k) => [k, deferred()]));
  const data = Object.fromEntries(Object.entries(files).map(([k, d]) => [k, d.promise]));
  data.all = Promise.all(["meta", "upcoming", "history", "events"].map((k) => data[k]));
  return { files, data };
}

function fakeBar() {
  const calls = [];
  const bar = {
    setMeta: () => calls.push("meta"),
    setTagCounts: () => calls.push("tagCounts"),
    setCount: (line) => calls.push(`count ${line.text}`),
    setError: () => calls.push("error"),
  };
  return { bar, calls };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

function start() {
  const { files, data } = fakeData();
  const { bar, calls } = fakeBar();
  const queue = [];
  const later = vi.fn((fn) => queue.push(fn));
  const selection = createState();
  const parts = { settle: vi.fn() };
  vi.spyOn(console, "error").mockImplementation(() => {});
  const numbers = connect({ data, selection, bar, parts, s: en, later });
  const flush = () => queue.splice(0).forEach((fn) => fn());
  return { files, calls, later, selection, parts, numbers, flush };
}

describe("a file that fails", () => {
  test("keeps its error line when the slower files arrive later", async () => {
    const { files, calls, numbers, flush } = start();
    files.meta.resolve(META);
    files.events.reject(new Error("events.json: HTTP 404")); // fast failure
    await tick();
    files.upcoming.resolve(GAMES); // slow successes
    files.history.resolve(HISTORY);
    expect(await numbers).toBeNull();
    flush();
    expect(calls.filter((c) => c.startsWith("count"))).toEqual([]);
    expect(calls.at(-1)).toBe("error");
  });

  test("replaces a count already drawn, and nothing redraws it", async () => {
    const { files, calls, selection, flush } = start();
    files.meta.resolve(META);
    files.upcoming.resolve(GAMES);
    files.history.resolve(HISTORY);
    await tick();
    flush();
    expect(calls.at(-1)).toMatch(/^count /);
    files.events.reject(new Error("events.json: HTTP 500"));
    await tick();
    selection.set({ group: "free" });
    selection.addTag(1);
    flush();
    expect(calls.at(-1)).toBe("error");
  });
});

describe("drawing the count", () => {
  async function loaded() {
    const run = start();
    run.files.meta.resolve(META);
    run.files.upcoming.resolve(GAMES);
    run.files.history.resolve(HISTORY);
    run.files.events.resolve([]);
    await run.numbers;
    return run;
  }

  test("waits for the paint after a change, and fast changes compute once", async () => {
    const { calls, later, selection, flush } = await loaded();
    expect(later).toHaveBeenCalledTimes(1); // the first count
    flush();
    expect(calls.filter((c) => c.startsWith("count"))).toHaveLength(1);
    selection.toggleLanguage("french");
    selection.toggleLanguage("german");
    selection.toggleLanguage("schinese");
    expect(later).toHaveBeenCalledTimes(2);
    expect(calls.filter((c) => c.startsWith("count"))).toHaveLength(1); // not yet
    flush();
    expect(calls.filter((c) => c.startsWith("count"))).toHaveLength(2);
  });

  test("paid / free is drawn at once, from the cached numbers", async () => {
    const { calls, later, selection, flush, numbers } = await loaded();
    flush();
    const shared = await numbers;
    const before = shared.get(selection.get());
    selection.set({ group: "free" });
    expect(later).toHaveBeenCalledTimes(1); // nothing new to compute
    expect(calls.at(-1)).toBe("count 0 of 0 upcoming · 0 of 0 past launches");
    expect(shared.get(selection.get())).toBe(before);
  });
});
