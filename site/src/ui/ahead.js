// Section 01, Competition ahead: the event band, the heatmap (an ARIA grid of
// plain HTML cells, laid out by CSS: weeks across, or down on phones) and the
// week detail. Numbers come from numbers.js, text and steps from heatview.js and
// weekdetail.js; this file only draws them and handles input.

import { formatNumber } from "../count.js";
import { bandEvents } from "../events.js";
import { buildView, eventText, formatCut, formatDate } from "../heatview.js";
import { toDay } from "../lib/dates.js";
import { WEEKS } from "../lib/heatmap.js";
import { tagNames } from "../tags.js";
import { detailItems, FIRST } from "../weekdetail.js";
import { h, uid } from "./dom.js";

const PHONE = "(max-width: 639px)";
const DAYS = 7;

export function aheadSection(s, body) {
  const a = s.ahead;
  const phone = window.matchMedia(PHONE);
  let numbers = null;
  let names = new Map();
  let events = null;
  let st = null; // the selection last drawn or asked for
  let rows = null; // heatmapRows drawn (an object from the cache)
  let view = null;
  let band = null;
  const local = { raw: false, year: false };
  let focus = { row: 0, week: 0 };
  let open = null; // { row, week, all }
  let cells = []; // [row][week] gridcell elements

  // ---------- fixed parts: toggles, legend, notes, detail ----------
  const toggle = (label, name) =>
    h(
      "label",
      { class: "ah-toggle" },
      h("input", {
        type: "checkbox",
        onchange: (e) => {
          local[name] = e.target.checked;
          if (st) redraw();
        },
      }),
      h("span", {}, label),
    );
  const sometime = h("p", { class: "ah-sometime" });
  const legend = h("div", { class: "ah-legend" });
  const controls = h(
    "div",
    { class: "ah-controls" },
    h("div", { class: "ah-toggles" }, toggle(a.raw, "raw"), toggle(a.yearLayer, "year"), sometime),
    legend,
  );
  const status = h("p", { class: "ah-status", role: "status" });
  const keyId = uid("hm-key");
  const scroller = h("div", { class: "hm-scroll" });
  const notes = h("div", { class: "ah-notes" });
  const detail = h("div", { class: "ah-detail" });
  // the opened week, said once (not the whole list) for screen readers
  const announce = h("p", { class: "visually-hidden", "aria-live": "polite" });
  const frame = [controls, status, scroller, notes, detail, announce];

  // ---------- the event band (desktop; phones list events in each week's row) ----------
  // Each event is a bar with its name above it, starting where it starts; a name
  // longer than its bar runs on to the right, so the next event of that kind goes
  // to a second row when the name would reach it.
  let weekPx = 0; // a week's width (with its gap) when the band was laid out
  let bandEl = null;
  let labelPx = () => 0; // an event name's width
  const measure = document.createElement("canvas").getContext("2d");

  // the events for the selection, rows packed for names `weekPx` wide a week
  function layoutBand() {
    const head = scroller.querySelector(".hm-week");
    weekPx = head ? head.getBoundingClientRect().width + 2 : Math.max(24, (scroller.clientWidth * 0.85) / WEEKS);
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    measure.font = `${0.75 * rem}px ${getComputedStyle(body).fontFamily}`;
    labelPx = (e) => measure.measureText(shortText(e)).width;
    const room = (e) => e.from + ((labelPx(e) + 0.75 * rem) / weekPx) * DAYS;
    band = bandEvents(events, rows[0].weeks[0], WEEKS, {
      tagNames: st.tags.map((t) => names.get(t)).filter(Boolean),
      languages: st.languages,
      extent: (e) => Math.max(e.to, room(e)),
    });
  }

  function placeBand(wrap) {
    layoutBand();
    const next = drawBand(rows[0].weeks[0]);
    if (bandEl?.parentNode === wrap) bandEl.remove();
    bandEl = next;
    if (next) wrap.prepend(next);
  }

  // a new width: names take a different share of the weeks
  new ResizeObserver(() => {
    const head = scroller.querySelector(".hm-week");
    const wrap = scroller.firstChild;
    if (head && wrap && Math.abs(head.getBoundingClientRect().width + 2 - weekPx) > 0.5) placeBand(wrap);
  }).observe(scroller);

  function drawBand(first) {
    if (!band.lanes.length) return null;
    const total = DAYS * WEEKS;
    const start = toDay(first);
    const lanes = band.lanes.map((lane, i) =>
      h(
        "div",
        { class: `hm-lane is-${lane.kind}` },
        h("span", { class: "hm-lane-name" }, lane.row === 0 ? a.kinds[lane.kind] : ""),
        h(
          "div",
          { class: "hm-track" },
          band.events
            .filter((e) => e.lane === i)
            .map((e) => {
              const from = Math.max(0, e.from - start);
              const to = Math.min(total, e.to - start);
              // a name that would run past the last week ends there instead
              const over = (from / DAYS) * weekPx + labelPx(e) - WEEKS * weekPx;
              return h(
                "span",
                {
                  class: "hm-event",
                  style: `left:${(100 * from) / total}%;width:${(100 * (to - from)) / total}%`,
                  title: `${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`,
                },
                h("span", { class: "hm-event-name", style: over > 0 ? `left:${-over}px` : null }, shortText(e)),
              );
            }),
        ),
      ),
    );
    return h("div", { class: "hm-band", "aria-hidden": "true" }, lanes);
  }

  // "Next Fest October", "China Spring Festival holiday (unconfirmed)"
  function shortText(e) {
    return eventText({ ...e, name: e.short }, s);
  }

  // ---------- the grid ----------
  function weekHead(w, i) {
    const label = [a.week(w.date, w.to)];
    if (w.current) label.push(a.thisWeek);
    if (w.far) label.push(a.far);
    if (w.events.length) label.push(a.events(w.events.map((e) => eventText(e, s)).join(", ")));
    return h(
      "div",
      {
        role: "columnheader",
        class: `hm-week${w.current ? " is-current" : ""}${w.far ? " is-far" : ""}`,
        style: `--wk:${i + 2}`,
        "aria-label": label.join(". "),
        "data-week": i,
      },
      h("span", { class: "hm-month", "aria-hidden": "true" }, w.month ?? ""),
      h("span", { class: "hm-day", "aria-hidden": "true" }, w.day),
      // phones: the whole date, this week, the far line and the events, as text
      h("span", { class: "hm-date", "aria-hidden": "true" }, w.date),
      w.current && h("span", { class: "hm-now", "aria-hidden": "true" }, a.thisWeek),
      i === view.weeks.findIndex((x) => x.far) && h("span", { class: "hm-far-note", "aria-hidden": "true" }, a.far),
      w.events.length > 0 &&
        h(
          "span",
          { class: "hm-week-events", "aria-hidden": "true" },
          w.events.map((e) => h("span", { class: `is-${e.kind}` }, shortText(e))),
        ),
    );
  }

  function rowHead(row, r) {
    return h(
      "div",
      { role: "rowheader", class: "hm-rowhead", style: `--tr:${r + 2}` },
      h("span", { class: "hm-row-name" }, row.label),
      h("span", { class: "hm-row-usual" }, row.usual),
      h(
        "span",
        { class: "hm-row-parts", "aria-hidden": "true" },
        view.parts.map((p) => h("span", {}, a.parts[p])),
      ),
    );
  }

  function cell(c, r, w) {
    const week = view.weeks[w];
    const el = h(
      "div",
      {
        role: "gridcell",
        class: `hm-cell${week.far ? " is-far" : ""}${week.current ? " is-current" : ""}`,
        style: `--tr:${r + 2};--wk:${w + 2}`,
        tabindex: r === focus.row && w === focus.week ? "0" : "-1",
        "aria-label": c.label,
        "aria-selected": String(!!open && open.row === r && open.week === w),
        onclick: () => {
          moveTo(r, w);
          openWeek(r, w);
        },
      },
      c.parts.map((p) =>
        h("span", { class: `hm-part is-${p.part} s${p.step}`, "aria-hidden": "true" }, h("span", {}, p.text)),
      ),
    );
    return el;
  }

  function drawGrid() {
    const nRows = view.rows.length;
    cells = view.rows.map((row, r) => row.cells.map((c, w) => cell(c, r, w)));
    const grid = h(
      "div",
      {
        class: "hm",
        role: "grid",
        "aria-labelledby": "ahead-title",
        "aria-describedby": keyId,
        "aria-rowcount": nRows + 1,
        style: `--rows:${nRows}`,
        onkeydown: keys,
        onfocusin: (e) => {
          const at = findCell(e.target);
          if (at) setFocus(at.row, at.week);
        },
      },
      h(
        "div",
        { role: "row", class: "hm-head" },
        h("div", { role: "columnheader", class: "hm-corner" }, h("span", {}, a.corner)),
        view.weeks.map(weekHead),
      ),
      view.rows.map((row, r) => h("div", { role: "row", class: "hm-row" }, rowHead(row, r), cells[r])),
    );
    const firstFar = view.weeks.findIndex((w) => w.far);
    const marks = h(
      "div",
      { class: "hm-marks", "aria-hidden": "true" },
      h("span", { class: "hm-mark-now", style: `--from:2;--to:${firstFar + 2}` }, a.thisWeek),
      h("span", { class: "hm-mark-far", style: `--from:${firstFar + 2};--to:-1` }, a.far),
    );
    const wrap = h("div", { class: "hm-wrap" }, marks, grid);
    scroller.replaceChildren(wrap);
    placeBand(wrap); // once the weeks have their width
  }

  function findCell(el) {
    for (let r = 0; r < cells.length; r++) {
      const w = cells[r].indexOf(el);
      if (w >= 0) return { row: r, week: w };
    }
    return null;
  }

  function setFocus(row, week) {
    cells[focus.row]?.[focus.week]?.setAttribute("tabindex", "-1");
    focus = { row, week };
    cells[row][week].setAttribute("tabindex", "0");
  }

  function moveTo(row, week) {
    const r = Math.max(0, Math.min(cells.length - 1, row));
    const w = Math.max(0, Math.min(cells[0].length - 1, week));
    setFocus(r, w);
    cells[r][w].focus();
  }

  // arrows follow the layout: weeks run across on wide screens, down on phones
  function keys(e) {
    const side = phone.matches;
    const { row, week } = focus;
    const step = {
      ArrowRight: side ? [1, 0] : [0, 1],
      ArrowLeft: side ? [-1, 0] : [0, -1],
      ArrowDown: side ? [0, 1] : [1, 0],
      ArrowUp: side ? [0, -1] : [-1, 0],
    }[e.key];
    if (step) moveTo(row + step[0], week + step[1]);
    else if (e.key === "Home") moveTo(e.ctrlKey ? 0 : row, 0);
    else if (e.key === "End") moveTo(e.ctrlKey ? cells.length - 1 : row, cells[0].length - 1);
    else if (e.key === "Enter" || e.key === " ") openWeek(row, week);
    else return;
    e.preventDefault();
  }

  // ---------- legend and notes ----------
  // the shades and where each starts (the cells say their numbers, so screen
  // readers skip the swatches)
  function drawLegend() {
    const swatch = (cls, text) => h("span", { class: "ah-swatch" }, h("span", { class: `hm-part ${cls}` }), h("span", {}, text));
    legend.replaceChildren(
      h("span", { class: "label" }, local.raw ? a.scaleRaw : a.scaleNormal),
      h(
        "span",
        { class: "ah-scale", "aria-hidden": "true" },
        [0, ...view.cuts].map((low, i) => swatch(`s${i}`, formatCut(low, s, local.raw))),
        local.year && swatch("is-year", a.parts.year),
      ),
    );
  }

  function drawNotes() {
    const lines = [a.key, local.year && a.keyYear, a.caveatNear, a.caveatFar, local.year && a.caveatYear];
    notes.replaceChildren(
      h("p", { id: keyId, class: "ah-key" }, lines.slice(0, 2).filter(Boolean).join(" ")),
      h("ul", { class: "ah-caveats" }, lines.slice(2).filter(Boolean).map((t) => h("li", {}, t))),
    );
    sometime.textContent = view.sometime.join(s.bar.sep);
  }

  // ---------- the week detail ----------
  function openWeek(row, week) {
    if (!view) return;
    const same = open && open.row === row && open.week === week;
    open = { row, week, all: same ? open.all : false };
    for (const [r, list] of cells.entries())
      list.forEach((el, w) => el.setAttribute("aria-selected", String(r === row && w === week)));
    markOpenWeek();
    drawDetail();
    if (!same) {
      const w = view.weeks[week];
      announce.textContent = `${a.week(w.date, w.to)}. ${detail.querySelector(".ah-detail-count").textContent}`;
      // just the heading into view, so the grid (and the focused cell) moves as little as it can
      detail.firstChild.scrollIntoView({ block: "nearest", behavior: reduceMotion() ? "auto" : "smooth" });
    }
  }

  function markOpenWeek() {
    for (const el of scroller.querySelectorAll(".is-open")) el.classList.remove("is-open");
    if (!open) return;
    scroller.querySelector(`.hm-week[data-week="${open.week}"]`)?.classList.add("is-open");
    for (const list of cells) list[open.week]?.classList.add("is-open");
  }

  function drawDetail() {
    if (!open) {
      detail.replaceChildren(h("p", { class: "quiet ah-hint" }, a.hint));
      return;
    }
    const w = view.weeks[open.week];
    const row = view.rows[open.row];
    const games = numbers.weekGames(st, row.tags, w.iso, local.year);
    const items = detailItems(games, numbers.game, s);
    const shown = open.all ? items : items.slice(0, FIRST);
    const parts = row.cells[open.week].parts;
    const list = h(
      "ol",
      { class: "ah-games" },
      shown.map((g) =>
        h(
          "li",
          {},
          h("a", { href: g.url, class: "ah-game" }, g.name),
          h(
            "span",
            { class: "ah-game-meta" },
            [[g.layer, g.date].filter(Boolean).join(" · "), g.followers].filter(Boolean).join(s.bar.sep),
          ),
          g.moved && h("span", { class: "ah-moved" }, g.moved),
        ),
      ),
    );
    const more =
      shown.length < items.length &&
      h(
        "button",
        {
          type: "button",
          class: "ah-more",
          onclick: () => {
            open.all = true;
            drawDetail();
            detail.querySelectorAll(".ah-game")[FIRST]?.focus();
          },
        },
        a.showAll(formatNumber(items.length, s)),
      );
    detail.replaceChildren(
      h(
        "div",
        { class: "ah-detail-head" },
        h("h3", {}, a.week(w.date, w.to)),
        h("p", { class: "ah-detail-for" }, a.detailFor(row.label, s.bar[st.group])),
        h(
          "p",
          { class: "ah-detail-cell" },
          parts.map((p) => `${a.parts[p.part]} ${p.text}`).join(s.bar.sep),
          local.raw ? "" : ` ${a.unitNormal}`,
        ),
      ),
      w.events.length > 0 &&
        h(
          "p",
          { class: "ah-detail-events" },
          h("span", { class: "label" }, a.detailEvents),
          " ",
          w.events.map((e) => `${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`).join("; "),
        ),
      h("p", { class: "ah-detail-count" }, items.length ? a.detailCount(a.games(formatNumber(items.length, s), items.length)) : a.detailNone),
      items.length > 0 && list,
      more,
    );
  }

  // ---------- drawing ----------
  function redraw() {
    const map = numbers.heatmap(st);
    if (map !== rows) {
      // a new pick of tags, mode or languages: the open week belonged to the old rows
      open = null;
      rows = map;
    }
    if (!body.dataset.drawn) {
      body.dataset.drawn = "true"; // in the page first, so the weeks can be measured
      body.replaceChildren(...frame);
    }
    layoutBand();
    const hadFocus = scroller.contains(document.activeElement);
    view = buildView(rows, { group: st.group, raw: local.raw, year: local.year, mode: st.mode, names, band: band.events, s });
    focus = {
      row: Math.min(focus.row, view.rows.length - 1),
      week: Math.min(focus.week, view.weeks.length - 1),
    };
    if (open && open.row >= view.rows.length) open = null;
    status.textContent = view.empty ?? "";
    const nothing = view.empty === a.empty;
    scroller.hidden = nothing;
    detail.hidden = nothing;
    if (!nothing) drawGrid();
    drawLegend();
    drawNotes();
    markOpenWeek();
    drawDetail();
    body.removeAttribute("aria-busy");
    if (hadFocus && !nothing) cells[focus.row][focus.week].focus({ preventScroll: true });
  }

  return {
    // the shared numbers and meta.json (tag names) are in
    start(shared, meta) {
      numbers = shared;
      names = tagNames(meta.tags);
    },
    setEvents(list) {
      events = list;
      if (st) redraw();
    },
    // draws the selection (its numbers are computed here unless cached)
    draw(selection) {
      st = selection;
      if (numbers && events) redraw();
    },
    // a new selection is being computed
    busy() {
      body.setAttribute("aria-busy", "true");
    },
  };
}

function reduceMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

