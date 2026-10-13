// What history says: the history panel (quiet, normal and busy weeks) and the
// launch timing lines from the model. The panel is the one numbers.js computed for
// the top bar's count, text from panelview.js; the lines come from timing.js. The
// shared raw counts toggle (top bar) sets the panel's measure.

import { panelView } from "../panelview.js";
import { timingLines } from "../timing.js";
import { fill, h, uid } from "./dom.js";

export function historySection(s, body) {
  const t = s.history;
  let numbers = null;
  let model; // undefined while loading, null when model.json is missing or broken
  let st = null;

  const panelTitle = uid("hs-panel");
  const timingTitle = uid("hs-timing");
  const panel = h("div", { class: "hs-panel" });
  const timing = h("div", { class: "hs-timing" });
  const frame = [
    h(
      "div",
      { class: "hs-col hs-col-panel", role: "group", "aria-labelledby": panelTitle },
      h("h3", { id: panelTitle }, t.panelTitle),
      panel,
    ),
    h(
      "div",
      { class: "hs-col hs-col-timing", role: "group", "aria-labelledby": timingTitle },
      h("h3", { id: timingTitle }, t.timingTitle),
      timing,
    ),
  ];

  // the lengths are shares of the largest 90th percentile; the numbers are in the cells
  function bars(b) {
    const pct = (x) => `${(x * 100).toFixed(1)}%`;
    return h(
      "span",
      { class: "hs-track" },
      h("span", { class: "hs-bar is-p90", style: `--w:${pct(b.p90)}` }),
      h("span", { class: "hs-bar is-p75", style: `--w:${pct(b.p75)}` }),
      h("span", { class: "hs-tick", style: `--x:${pct(b.median)}` }),
    );
  }

  function head(key) {
    return h(
      "th",
      { scope: "col", class: "hs-num" },
      h("span", { class: "hs-long" }, t.heads[key]),
      h("span", { class: "hs-short", "aria-hidden": "true" }, t.headsShort[key]),
    );
  }

  function drawPanel() {
    const v = panelView(numbers.get(st).panel, st.group, s, { tags: st.tags });
    if (!v.shown) {
      fill(panel, h("p", { class: "hs-few" }, v.text));
      return;
    }
    fill(
      panel,
      h("p", { class: "hs-intro" }, v.intro),
      h(
        "table",
        { class: "hs-table" },
        h("caption", { class: "visually-hidden" }, t.caption),
        h(
          "thead",
          {},
          h(
            "tr",
            {},
            h("th", { scope: "col", class: "hs-part-head" }, t.heads.part),
            head("p75"),
            head("p90"),
            head("median"),
            head("games"),
            h("td", { class: "hs-bar-cell", "aria-hidden": "true" }),
          ),
        ),
        h(
          "tbody",
          {},
          v.rows.map((r) =>
            h(
              "tr",
              { class: `is-${r.part}` },
              h("th", { scope: "row" }, h("span", { class: "hs-part" }, r.name), h("span", { class: "hs-range" }, r.range)),
              h("td", { class: "hs-num hs-lead" }, r.p75),
              h("td", { class: "hs-num hs-lead" }, r.p90),
              h("td", { class: "hs-num" }, r.median),
              h("td", { class: "hs-num hs-games" }, r.games),
              h("td", { class: "hs-bar-cell", "aria-hidden": "true" }, bars(r.bars)),
            ),
          ),
        ),
      ),
      h("p", { class: "hs-cuts" }, v.cuts),
      h("p", { class: "hs-read quiet" }, v.read, h("span", { class: "hs-bars-key" }, " ", t.barsKey)),
    );
  }

  function drawTiming() {
    if (model === undefined) {
      fill(timing, h("p", { class: "quiet" }, s.bar.loading));
      return;
    }
    const v = timingLines(model, st.group, { languages: st.languages }, s);
    if (!v.ready) {
      fill(timing, h("p", { class: "hs-not-ready" }, v.text));
      return;
    }
    fill(
      timing,
      h("p", { class: "hs-for" }, v.heading),
      h(
        "ul",
        { class: "hs-lines" },
        v.lines.map((line) => h("li", {}, line)),
      ),
      v.china && h("p", { class: "hs-china" }, v.china),
      h("p", { class: "hs-caveat quiet" }, v.caveat),
    );
  }

  function redraw() {
    if (!body.dataset.drawn) {
      body.dataset.drawn = "true";
      fill(body, h("div", { class: "hs" }, frame));
    }
    drawPanel();
    drawTiming();
    body.removeAttribute("aria-busy");
  }

  return {
    start(shared) {
      numbers = shared;
    },
    // model.json, or null when it is missing or broken
    setModel(m) {
      model = m;
      if (st && numbers) drawTiming();
    },
    draw(selected) {
      st = selected;
      if (numbers) redraw();
    },
    busy() {
      body.setAttribute("aria-busy", "true");
    },
  };
}
