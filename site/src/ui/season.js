// Typical for this time of year: the seasonal outlook for the next 26 weeks, a bar
// per week from 1.0 (a usual week) to its value with its spread behind it, the
// events lanes under it, and what each week rests on. The weeks are a listbox: one
// tab stop, arrow keys move. Wide screens draw weeks across; under 1024px they run
// down, and the picked week shows what it rests on in its own row. Numbers come
// from numbers.js (season.js outlook), text from outlookview.js.

import { bandEvents } from "../events.js";
import { outlookView } from "../outlookview.js";
import { tagNames } from "../tags.js";
import { fill, h, uid } from "./dom.js";
import { laneItems } from "./lanes.js";

const NONE = []; // the events when events.json failed: one list, so the cached outlook is kept

export function seasonSection(s, body) {
  const t = s.season;
  let numbers = null;
  let names = new Map();
  let events; // undefined while loading, null if events.json failed
  let st = null;
  let view = null;
  let drawnFor = null; // [outlook, group, band] last drawn
  let picked = 0;
  let options = [];

  const keyLine = h("p", { class: "ol-key" }, t.key);
  const from = h("p", { class: "ol-from quiet" });
  const note = h("p", { class: "ol-note quiet" });
  const chart = h("div", { class: "ol-scroll" });
  const detail = h("div", { class: "ol-detail", "aria-hidden": "true" });
  const labelId = uid("ol-label");
  const frame = [h("p", { id: labelId, class: "visually-hidden" }, t.label), keyLine, from, note, chart, detail];

  function showDetail(i) {
    const w = view.weeks[i];
    fill(
      detail,
      h("p", { class: "ol-detail-week" }, w.detail),
      w.drivers && h("p", { class: "ol-detail-from" }, w.drivers),
      w.eventsFull.length > 0 && h("p", { class: "ol-detail-events" }, s.ahead.events(w.eventsFull.join(", "))),
    );
  }

  function pick(i, focus = true) {
    const n = Math.max(0, Math.min(options.length - 1, i));
    options[picked]?.setAttribute("tabindex", "-1");
    options[picked]?.setAttribute("aria-selected", "false");
    options[picked]?.classList.remove("is-picked");
    picked = n;
    options[n].setAttribute("tabindex", "0");
    options[n].setAttribute("aria-selected", "true");
    options[n].classList.add("is-picked");
    if (focus) options[n].focus();
    showDetail(n);
  }

  function keys(e) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step) pick(picked + step);
    else if (e.key === "Home") pick(0);
    else if (e.key === "End") pick(options.length - 1);
    else return;
    e.preventDefault();
  }

  // the bar from 1.0 to the value and the spread, as shares of the plot (0 the
  // lowest value on the scale, 100 the highest): the CSS lays them up or across
  function barStyle(bar) {
    const at = (x) => `${(((Math.max(-1, Math.min(1, x)) + 1) / 2) * 100).toFixed(2)}%`;
    return [
      `--a:${at(Math.min(0, bar.v))}`,
      `--b:${at(Math.max(0, bar.v))}`,
      `--lo:${at(bar.lo)}`,
      `--hi:${at(bar.hi)}`,
    ].join(";");
  }

  function option(w, i) {
    return h(
      "div",
      {
        role: "option",
        class: `ol-week${w.current ? " is-current" : ""}${i === picked ? " is-picked" : ""}`,
        style: `--wk:${i + 2}${w.bar ? `;${barStyle(w.bar)}` : ""}`,
        tabindex: i === picked ? "0" : "-1",
        "aria-selected": String(i === picked),
        "aria-label": w.label,
        onclick: () => pick(i),
        onmouseenter: () => showDetail(i),
        onfocus: () => i !== picked && pick(i, false),
      },
      h("span", { class: "ol-day", "aria-hidden": "true" }, h("span", { class: "ol-date" }, w.date), h("span", { class: "ol-dom" }, w.day)),
      h(
        "span",
        { class: "ol-plot", "aria-hidden": "true" },
        h("span", { class: "ol-mid" }),
        w.bar && h("span", { class: "ol-spread" }),
        w.bar && h("span", { class: "ol-bar" }),
      ),
      h("span", { class: "ol-value", "aria-hidden": "true" }, w.value),
      w.events.length > 0 &&
        h(
          "span",
          { class: "ol-events", "aria-hidden": "true" },
          w.events.map((e) => h("span", {}, e)),
        ),
      w.drivers && h("span", { class: "ol-drivers", "aria-hidden": "true" }, w.drivers),
    );
  }

  function draw(band) {
    options = view.weeks.map(option);
    const months = view.weeks.map(
      (w, i) => w.month && h("span", { class: "ol-month", style: `--wk:${i + 2}`, "aria-hidden": "true" }, w.month),
    );
    fill(
      chart,
      h(
        "div",
        { class: "ol", style: `--weeks:${view.weeks.length}` },
        h("span", { class: "ol-corner", "aria-hidden": "true" }, s.ahead.corner),
        months,
        h("span", { class: "ol-axis", "aria-hidden": "true" }, "1.0"),
        h(
          "div",
          { class: "ol-list", role: "listbox", "aria-labelledby": labelId, "aria-orientation": "horizontal", onkeydown: keys },
          options,
        ),
        h("div", { class: "ol-band", "aria-hidden": "true" }, laneItems(band, 3, s)),
      ),
    );
    chart.querySelector(".ol").addEventListener("mouseleave", () => showDetail(picked));
    showDetail(picked);
  }

  function redraw() {
    if (events === undefined) return; // the pattern uses the events: wait for them
    if (!body.dataset.drawn) {
      body.dataset.drawn = "true";
      fill(body, frame);
    }
    const list = events ?? NONE;
    const outlook = numbers.outlook(st, list);
    const band = bandEvents(list, outlook.weeks[0], outlook.weeks.length, {
      tagNames: st.tags.map((x) => names.get(x)).filter(Boolean),
      languages: st.languages,
    });
    const key = [outlook, st.group, JSON.stringify(band.events.map((e) => e.name))];
    from.textContent = t.from(t[st.group]);
    note.textContent = events === null ? t.eventsFailed : "";
    body.removeAttribute("aria-busy");
    if (drawnFor && key.every((k, i) => k === drawnFor[i])) return;
    drawnFor = key;
    const hadFocus = chart.contains(document.activeElement);
    view = outlookView(outlook, st.group, { events: list, band: band.events, languages: st.languages }, s);
    picked = Math.min(picked, view.weeks.length - 1);
    draw(band);
    if (hadFocus) options[picked].focus({ preventScroll: true });
  }

  return {
    start(shared, meta) {
      numbers = shared;
      names = tagNames(meta.tags);
    },
    // events.json's list, or null if it failed: the pattern goes without events
    setEvents(list) {
      events = list;
      if (st && numbers) redraw();
    },
    // true when drawing `selected` would compute the outlook (not cached yet)
    pending: (selected) => events !== undefined && !numbers?.hasOutlook(selected, events ?? NONE),
    draw(selected) {
      st = selected;
      if (numbers) redraw();
    },
    busy() {
      body.setAttribute("aria-busy", "true");
    },
  };
}
