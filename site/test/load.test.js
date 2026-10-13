import { expect, test, vi } from "vitest";
import { loadData } from "../src/load.js";

const FILES = {
  "meta.json": { snapshot_date: "2026-10-13", tags: [[19, "Action", 1, 1]], languages: ["english"] },
  "upcoming.json": { columns: ["appid", "tags", "langs"], rows: [[1, [0], [0]]] },
  "history.json": { columns: ["appid", "tags", "langs"], rows: [[2, [0], [0]]] },
  "events.json": [],
  "model.json": { paid: {} },
};

function fakeFetch(files) {
  return vi.fn(async (url) => {
    const name = url.split("/").pop();
    return name in files
      ? { ok: true, status: 200, json: async () => files[name] }
      : { ok: false, status: 404, json: async () => null };
  });
}

test("every file is asked for at once", () => {
  const fetchFn = fakeFetch(FILES);
  loadData("/base/data/", fetchFn);
  expect(fetchFn.mock.calls.map(([u]) => u).sort()).toEqual(
    ["events", "history", "meta", "model", "upcoming"].map((n) => `/base/data/${n}.json`),
  );
});

test("games and launches come back with tag ids and language codes", async () => {
  const data = loadData("", fakeFetch(FILES));
  expect(await data.upcoming).toEqual([{ appid: 1, tags: [19], langs: ["english"] }]);
  expect(await data.history).toEqual([{ appid: 2, tags: [19], langs: ["english"] }]);
  await expect(data.all).resolves.toHaveLength(3);
});

test("model.json is optional", async () => {
  const { "model.json": _, ...rest } = FILES;
  const data = loadData("", fakeFetch(rest));
  expect(await data.model).toBeNull();
  await expect(data.all).resolves.toBeDefined();
});

test("events.json is optional too: missing, the page goes on without the events lanes", async () => {
  const { "events.json": _, ...rest } = FILES;
  const data = loadData("", fakeFetch(rest));
  expect(await data.events).toBeNull();
  await expect(data.all).resolves.toBeDefined();
});

test("a missing required file fails `all`, once, without unhandled rejections", async () => {
  const { "history.json": _, ...rest } = FILES;
  const data = loadData("", fakeFetch(rest));
  await expect(data.all).rejects.toThrow("history.json");
  expect(await data.meta).toEqual(FILES["meta.json"]);
});
