// Fetching the site's data files (analysis/site_data.py and analysis/model.py
// write them). All start at once; each part of the page waits only for what it needs.

import { fromTable } from "./lib/data.js";

export const REQUIRED = ["meta", "upcoming", "history", "events"];

// Promises for each file, parsed: upcoming and history as rows with tag ids and
// language codes. model.json is optional: missing or broken, it resolves to null.
export function loadData(base, fetchFn = fetch) {
  const get = (name) =>
    fetchFn(`${base}${name}.json`).then((r) => {
      if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`);
      return r.json();
    });
  const meta = get("meta");
  const upcoming = get("upcoming");
  const history = get("history");
  const events = get("events");
  const model = get("model").catch(() => null);
  const data = {
    meta,
    upcoming: Promise.all([meta, upcoming]).then(([m, t]) => fromTable(t, m)),
    history: Promise.all([meta, history]).then(([m, t]) => fromTable(t, m)),
    events,
    model,
  };
  // resolves when every required file is in, rejects on the first that fails
  data.all = Promise.all(REQUIRED.map((k) => data[k]));
  // a failure is reported once, through `all`; the others must not be unhandled
  for (const k of REQUIRED) data[k].catch(() => {});
  return data;
}
