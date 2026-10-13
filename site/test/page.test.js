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
  data.all = Promise.all(["meta", "upcoming", "history"].map((k) => data[k]));
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
    files.history.reject(new Error("history.json: HTTP 404")); // fast failure
    await tick();
    files.upcoming.resolve(GAMES); // slow success
    expect(await numbers).toBeNull();
    flush();
    expect(calls.filter((c) => c.startsWith("count"))).toEqual([]);
    expect(calls.at(-1)).toBe("error");
  });

  test("events.json is optional: without it (loadData gives null) the count still draws", async () => {
    const { files, calls, selection, flush } = start();
    files.events.resolve(null);
    files.meta.resolve(META);
    files.upcoming.resolve(GAMES);
    files.history.resolve(HISTORY);
    await tick();
    flush();
    selection.addTag(1);
    flush();
    expect(calls).not.toContain("error");
    expect(calls.at(-1)).toMatch(/^count /);
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

describe("section 01", () => {
  // a fake section: records what connect asks of it
  function fakeAhead() {
    const calls = [];
    return {
      calls,
      start: (numbers, meta) => calls.push(`start ${meta.snapshot_date}`),
      setEvents: (events) => calls.push(`events ${events?.length ?? "failed"}`),
      draw: (st) => calls.push(`draw ${st.group} ${st.tags.join(",")}`),
      busy: () => calls.push("busy"),
    };
  }

  function startWith(ahead) {
    const { files, data } = fakeData();
    const { bar, calls } = fakeBar();
    bar.setSummary = (line) => calls.push(`summary ${line}`);
    const queue = [];
    const selection = createState();
    vi.spyOn(console, "error").mockImplementation(() => {});
    const parts = { settle: vi.fn() };
    const numbers = connect({ data, selection, bar, parts, ahead, s: en, later: (fn) => queue.push(fn) });
    const flush = () => queue.splice(0).forEach((fn) => fn());
    return { files, calls, selection, numbers, flush };
  }

  test("gets the numbers, the events, and each selection after the paint, with the summary", async () => {
    const ahead = fakeAhead();
    const { files, calls, selection, numbers, flush } = startWith(ahead);
    files.meta.resolve(META);
    files.upcoming.resolve(GAMES);
    files.history.resolve(HISTORY);
    files.events.resolve([{ name: "x" }]);
    const shared = await numbers;
    await tick();
    expect(ahead.calls.slice(0, 3)).toEqual(["start 2026-10-13", "busy", "events 1"]);
    flush();
    expect(ahead.calls.at(-1)).toBe("draw paid ");
    expect(calls.at(-1)).toBe("summary All tags · Paid · 1 upcoming");
    shared.heatmap(selection.get()); // what the real section computes when it draws
    selection.set({ group: "free" }); // both cached: drawn at once
    expect(ahead.calls.at(-1)).toBe("draw free ");
    selection.addTag(1); // new numbers: busy, then drawn after the paint
    expect(ahead.calls.at(-1)).toBe("busy");
    flush();
    expect(ahead.calls.at(-1)).toBe("draw free 1");
  });

  test("never draws after a file fails", async () => {
    const ahead = fakeAhead();
    const { files, numbers, flush } = startWith(ahead);
    files.meta.resolve(META);
    files.history.reject(new Error("history.json: HTTP 404"));
    await tick();
    files.upcoming.resolve(GAMES);
    files.events.resolve([]);
    expect(await numbers).toBeNull();
    flush();
    expect(ahead.calls).toEqual([]);
  });

  test("hears that events.json failed (null) and still draws", async () => {
    const ahead = fakeAhead();
    const { files, numbers, flush } = startWith(ahead);
    files.meta.resolve(META);
    files.upcoming.resolve(GAMES);
    files.history.resolve(HISTORY);
    files.events.resolve(null);
    await numbers;
    await tick();
    flush();
    expect(ahead.calls).toContain("events failed");
    expect(ahead.calls.at(-1)).toBe("draw paid ");
  });
});
