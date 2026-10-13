// Joins the data, the selection and the top bar. Kept apart from main.js so the
// order of events (a file failing while others load, fast clicks) can be tested.

import { countLine, summaryLine, tooFewPast } from "./count.js";
import { createNumbers } from "./numbers.js";

// after the browser has painted the click (the chip or switch shows at once), then
// off that frame; changes made meanwhile are drawn once
export function afterPaint(fn) {
  requestAnimationFrame(() => setTimeout(fn, 0));
}

// data: loadData's promises. bar: setMeta, setTagCounts, setCount, setError (and
// setSummary). parts: settle. history (What history says): start, setModel, draw,
// busy. season (Typical for this time of year): start, setEvents, pending, draw,
// busy. ahead (Competition ahead): start, setEvents, setModel (optional), draw, busy.
// trends (Trends): start, draw, busy.
// Returns a promise for the shared numbers (null if the data failed).
export function connect({
  data,
  selection,
  bar,
  parts,
  foot,
  history = null,
  season = null,
  ahead = null,
  trends = null,
  s,
  later = afterPaint,
}) {
  let failed = false;
  const quiet = () => {}; // a failed file is reported once, by data.all below

  data.meta.then((meta) => {
    bar.setMeta(meta);
    foot?.setDate(meta.snapshot_date);
  }, quiet);

  data.all.then(parts.settle, (err) => {
    failed = true; // nothing drawn later may hide the error line
    console.error(err);
    bar.setError();
    parts.settle();
  });

  return Promise.all([data.meta, data.upcoming, data.history]).then(([meta, games, past]) => {
    if (failed) return null;
    const numbers = createNumbers(games, past, meta.snapshot_date);
    bar.setTagCounts((st) => numbers.tagCounts(st));
    history?.start(numbers);
    trends?.start(numbers);
    for (const part of [season, ahead]) {
      if (!part) continue;
      part.start(numbers, meta);
      data.events.then((events) => !failed && part.setEvents(events), quiet);
    }
    // model.json: the lines in What history says, and the lane tooltips in Competition ahead
    for (const part of [history, ahead]) {
      if (part?.setModel) data.model.then((model) => !failed && part.setModel(model), quiet);
    }
    let waiting = false;
    const draw = () => {
      waiting = false;
      if (failed) return;
      const st = selection.get();
      const { counts, panel } = numbers.get(st);
      bar.setCount(countLine(counts, st.group, s), tooFewPast(panel, st.group));
      bar.setSummary?.(summaryLine(st, counts, s));
      history?.draw(st);
      season?.draw(st);
      ahead?.draw(st);
      trends?.draw(st);
    };
    // already known (paid / free, or back to an earlier pick): drawn now
    const known = (st) =>
      numbers.has(st) &&
      (!ahead || numbers.hasHeatmap(st)) &&
      (!season || !season.pending(st)) &&
      (!trends || numbers.hasTrends(st));
    selection.subscribe((st) => {
      if (known(st)) draw();
      else {
        history?.busy();
        season?.busy();
        ahead?.busy();
        trends?.busy();
        if (!waiting) {
          waiting = true;
          later(draw);
        }
      }
    });
    return numbers;
  }, () => null);
}
