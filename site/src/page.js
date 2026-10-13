// Joins the data, the selection and the top bar. Kept apart from main.js so the
// order of events (a file failing while others load, fast clicks) can be tested.

import { countLine, tooFewPast } from "./count.js";
import { createNumbers } from "./numbers.js";

// after the browser has painted the click (the chip or switch shows at once), then
// off that frame; changes made meanwhile are drawn once
export function afterPaint(fn) {
  requestAnimationFrame(() => setTimeout(fn, 0));
}

// data: loadData's promises. bar: setMeta, setTagCounts, setCount, setError.
// parts: settle. Returns a promise for the shared numbers (null if the data failed).
export function connect({ data, selection, bar, parts, foot, s, later = afterPaint }) {
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

  return Promise.all([data.upcoming, data.history]).then(([games, history]) => {
    if (failed) return null;
    const numbers = createNumbers(games, history);
    bar.setTagCounts((st) => numbers.tagCounts(st));
    let waiting = false;
    const draw = () => {
      waiting = false;
      if (failed) return;
      const st = selection.get();
      const { counts, panel } = numbers.get(st);
      bar.setCount(countLine(counts, st.group, s), tooFewPast(panel, st.group));
    };
    selection.subscribe((st) => {
      if (numbers.has(st)) draw(); // already known (paid / free, or back to an earlier pick): now
      else if (!waiting) {
        waiting = true;
        later(draw);
      }
    });
    return numbers;
  }, () => null);
}
