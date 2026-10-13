// Trends: the selection's past launches per quarter since 2022, as a share of all
// launches (the default: Steam grows every year, so raw counts rise for almost every
// tag), as counts, or added up. A bar per quarter up from 0; the recent quarters (the
// one under way, labelled "so far", and the two before it) are hatched and marked
// "may still change"; nothing is drawn ahead. The quarters are a
// listbox (one tab stop, arrow keys), each labelled with its numbers, and the line
// over the chart reads out the picked or pointed-at quarter. Numbers come from
// numbers.js (lib/trends.js quarterly), text from trendview.js.

import { trendView, VIEWS, viewsFor } from "../trendview.js";
import { fill, h, uid } from "./dom.js";
import { sectionNumber } from "./sections.js";

const pct = (x) => `${(Math.max(0, Math.min(1, x)) * 100).toFixed(2)}%`;

export function trendsSection(s, body) {
  const t = s.trends;
  let numbers = null;
  let st = null;
  let view = "share"; // the view picked; with no tags there is no share, and picking a tag brings it back
  let hadTags = false;
  let picked = -1; // -1 until the first draw picks the last quarter before the recent ones
  let options = [];
  let bars = [];
  let drawnFor = null;

  const labelId = uid("tr-label");
  const name = uid("tr-view");
  const inputs = VIEWS.map((v) =>
    h("input", {
      type: "radio",
      name,
      value: v,
      onchange: () => {
        view = v;
        redraw();
      },
    }),
  );
  const choices = VIEWS.map((v, i) => h("label", {}, inputs[i], h("span", {}, t.views[v])));
  const switcher = h(
    "fieldset",
    { class: "ctl tr-views" },
    h("legend", { class: "label" }, t.show),
    h("div", { class: "seg is-many" }, choices),
  );
  const fallback = h("p", { class: "tr-fallback quiet" });
  const summary = h("p", { class: "tr-summary" });
  const readout = h("p", { class: "tr-readout", "aria-hidden": "true" });
  const chart = h("div", { class: "tr-scroll" });
  const partial = h("p", {});
  const notes = h(
    "div",
    { class: "tr-notes quiet" },
    partial,
    h("p", {}, t.noForecast),
    h("p", {}, t.tags),
    h("p", {}, t.removed),
    h("p", {}, t.which(sectionNumber("history"))),
  );
  const frame = [h("p", { id: labelId, class: "visually-hidden" }, t.label), switcher, fallback, summary, readout, chart, notes];

  function showReadout(i) {
    readout.textContent = bars[i]?.label ?? "";
  }

  function pick(i, focus = true) {
    const n = Math.max(0, Math.min(options.length - 1, i));
    const old = options[picked];
    old?.setAttribute("tabindex", "-1");
    old?.setAttribute("aria-selected", "false");
    old?.classList.remove("is-picked");
    picked = n;
    options[n].setAttribute("tabindex", "0");
    options[n].setAttribute("aria-selected", "true");
    options[n].classList.add("is-picked");
    if (focus) options[n].focus();
    showReadout(n);
  }

  function keys(e) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step) pick(picked + step);
    else if (e.key === "Home") pick(0);
    else if (e.key === "End") pick(options.length - 1);
    else return;
    e.preventDefault();
  }

  function option(b, i) {
    return h(
      "div",
      {
        role: "option",
        class: `tr-q${b.recent ? " is-recent" : ""}${b.partial ? " is-partial" : ""}${b.over ? " is-over" : ""}${i === picked ? " is-picked" : ""}`,
        style: `--i:${i + 2};--h:${pct(b.value)}`,
        tabindex: i === picked ? "0" : "-1",
        "aria-selected": String(i === picked),
        "aria-label": b.label,
        onclick: () => pick(i),
        onmouseenter: () => showReadout(i),
        onfocus: () => i !== picked && pick(i, false),
      },
      h("span", { class: "tr-plot", "aria-hidden": "true" }, h("span", { class: "tr-bar" }), b.over && h("span", { class: "tr-cut" })),
      h(
        "span",
        { class: "tr-name", "aria-hidden": "true" },
        h("span", { class: "tr-short" }, b.short),
        b.partial && h("span", { class: "tr-sofar" }, t.soFar),
      ),
    );
  }

  function draw(v) {
    bars = v.bars;
    if (picked < 0 || picked >= bars.length) picked = Math.max(0, (v.recent.span ? v.recent.from : bars.length) - 1);
    options = bars.map(option);
    fill(
      chart,
      h(
        "div",
        { class: "tr", style: `--n:${bars.length}`, onmouseleave: () => showReadout(picked) },
        v.recent.span > 0 && [
          h("span", { class: "tr-recent-label", "aria-hidden": "true" }, t.recent),
          h("span", { class: "tr-recent", style: `--from:${v.recent.from + 2};--span:${v.recent.span}`, "aria-hidden": "true" }),
        ],
        h(
          "div",
          { class: "tr-grid", "aria-hidden": "true" },
          v.ticks.map((tk, i) =>
            h("span", { class: `tr-line${i === 0 ? " is-zero" : ""}`, style: `--y:${pct(tk.at)}` }, h("span", { class: "tr-tick" }, tk.text)),
          ),
        ),
        h(
          "div",
          { class: "tr-list", role: "listbox", "aria-labelledby": labelId, "aria-orientation": "horizontal", onkeydown: keys },
          options,
        ),
        v.years.map((y) =>
          h("span", { class: "tr-year", style: `--from:${y.from + 2};--span:${y.span}`, "aria-hidden": "true" }, String(y.year)),
        ),
      ),
    );
    showReadout(picked);
  }

  function redraw() {
    if (!numbers || !st) return;
    if (!body.dataset.drawn) {
      body.dataset.drawn = "true";
      fill(body, frame);
    }
    if (st.tags.length && !hadTags) view = "share"; // a tag picked: the share is back, and first
    hadTags = st.tags.length > 0;
    const q = numbers.trends(st);
    const v = trendView(q, st.group, view, s, { tags: st.tags, languages: st.languages });
    const offered = viewsFor(st.tags);
    inputs.forEach((input, i) => {
      input.checked = VIEWS[i] === v.view;
      choices[i].hidden = !offered.includes(VIEWS[i]);
    });
    fallback.textContent = st.tags.length ? "" : t.noShare;
    summary.textContent = v.empty ? "" : (v.summary ?? "");
    summary.classList.toggle("is-few", v.few);
    partial.textContent = v.partial ?? "";
    body.removeAttribute("aria-busy");
    const key = [q, st.group, v.view, st.languages.join()];
    if (drawnFor && key.every((k, i) => k === drawnFor[i])) return;
    drawnFor = key;
    if (v.empty) {
      bars = [];
      options = [];
      readout.textContent = "";
      fill(chart, h("p", { class: "tr-empty" }, v.empty));
      return;
    }
    const hadFocus = chart.contains(document.activeElement);
    draw(v);
    if (hadFocus) options[picked].focus({ preventScroll: true });
  }

  return {
    start(shared) {
      numbers = shared;
    },
    draw(selected) {
      st = selected;
      redraw();
    },
    busy() {
      body.setAttribute("aria-busy", "true");
    },
  };
}
