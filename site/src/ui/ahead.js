// Competition ahead: the heatmap (an ARIA grid of plain HTML cells, laid out by
// CSS: weeks across, or down on phones), the events lanes under the dates, and the
// week's games. Numbers come from numbers.js, text and steps from heatview.js and
// weekdetail.js, the events from events.js; this file only draws them and handles
// input.

import { formatNumber } from "../count.js";
import { bandEvents } from "../events.js";
import { buildView, CUTS, eventText, formatCut, formatDate } from "../heatview.js";
import { WEEKS } from "../lib/heatmap.js";
import { tagNames } from "../tags.js";
import { detailItems, listParts } from "../weekdetail.js";
import { fill, h, uid } from "./dom.js";

const PHONE = "(max-width: 639px)";

export function aheadSection(s, body) {
  const a = s.ahead;
  const phone = window.matchMedia(PHONE);
  let numbers = null;
  let names = new Map();
  let events; // undefined while loading, null if events.json failed
  let st = null; // the selection last drawn or asked for
  let rows = null; // heatmapRows drawn (an object from the cache)
  let band = { events: [], lanes: [] };
  let bandFor = null; // [rows, events] the band was picked for
  let view = null;
  const local = { raw: false, year: false };
  let focus = { row: 0, week: 0 };
  let open = null; // { row, week, parts: Set of list parts shown in full }
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
  const eventsNote = h("p", { class: "ah-events-note quiet" });
  const keyId = uid("hm-key");
  const scroller = h("div", { class: "hm-scroll" });
  const notes = h("div", { class: "ah-notes" });
  const detail = h("div", { class: "ah-detail" });
  // the opened week, said once (not the whole list) for screen readers
  const announce = h("p", { class: "visually-hidden", "aria-live": "polite" });
  const frame = [controls, status, eventsNote, scroller, notes, detail, announce];

  // ---------- the grid ----------
  // Desktop rows: 1 the dates; then, with events, the "Events" label, one row per
  // lane and a rule; then the heatmap rows. Phones put weeks in rows and the
  // heatmap rows in columns 2 on (--tc); the lanes are hidden there.
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
      h("span", { class: "hm-date", "aria-hidden": "true" }, w.date),
      // phones: this week, the far line and the events, as text in the week's row
      w.current && h("span", { class: "hm-now", "aria-hidden": "true" }, a.thisWeek),
      i === firstFar(view) && h("span", { class: "hm-far-note", "aria-hidden": "true" }, a.far),
      w.events.length > 0 &&
        h(
          "span",
          { class: "hm-week-events", "aria-hidden": "true" },
          w.events.map((e) => h("span", { class: `hm-tag is-${e.kind}` }, eventText({ ...e, name: e.short }, s))),
        ),
    );
  }

  function rowHead(row, r, tr) {
    return h(
      "div",
      { role: "rowheader", class: `hm-rowhead${row.counts ? " is-counts" : ""}`, style: `--tr:${tr};--tc:${r + 2}` },
      h("span", { class: "hm-row-name", lang: s.lang }, row.label),
      h("span", { class: "hm-row-note" }, row.note),
      h(
        "span",
        { class: "hm-row-parts", "aria-hidden": "true" },
        view.parts.map((p) => h("span", {}, a.parts[p])),
      ),
    );
  }

  function cell(c, r, w, tr) {
    const week = view.weeks[w];
    return h(
      "div",
      {
        role: "gridcell",
        class: `hm-cell${week.far ? " is-far" : ""}`,
        style: `--tr:${tr};--tc:${r + 2};--wk:${w + 2}`,
        tabindex: r === focus.row && w === focus.week ? "0" : "-1",
        "aria-label": c.label,
        "aria-selected": String(!!open && open.row === r && open.week === w),
        onclick: () => {
          moveTo(r, w);
          openWeek(r, w);
        },
      },
      c.parts.map((p) =>
        h(
          "span",
          { class: `hm-part is-${p.part} s${p.step}`, "aria-hidden": "true" },
          h("span", { class: "hm-part-tag" }, a.partsShort[p.part]),
          h("span", { class: "hm-num" }, p.text),
        ),
      ),
    );
  }

  // the events lanes: a block over the weeks each event covers, its name from its
  // first week up to the next event in the lane (cut short with an ellipsis there)
  function lanes(first) {
    if (!band.lanes.length) return [];
    const out = [h("div", { class: "hm-band-label", style: `--tr:${first}` }, a.eventsLabel)];
    band.lanes.forEach((lane, i) => {
      const tr = first + 1 + i;
      out.push(h("div", { class: "hm-lane-name", style: `--tr:${tr}` }, lane.row === 0 ? a.kinds[lane.kind] : ""));
      for (const e of band.events.filter((x) => x.lane === i)) {
        const full = `${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`;
        out.push(
          h("div", {
            class: `hm-block is-${e.kind}`,
            style: `--tr:${tr};--from:${e.weeks[0] + 2};--to:${e.weeks[1] + 3}`,
          }),
          h(
            "div",
            { class: "hm-block-name", style: `--tr:${tr};--from:${e.weeks[0] + 2};--to:${e.room + 2}`, title: full },
            eventText({ ...e, name: e.short }, s),
          ),
        );
      }
    });
    out.push(h("div", { class: "hm-band-rule", style: `--tr:${first + 1 + band.lanes.length}` }));
    return out;
  }

  function drawGrid() {
    const nRows = view.rows.length;
    const top = band.lanes.length ? band.lanes.length + 4 : 2; // the first heatmap row's line
    cells = view.rows.map((row, r) => row.cells.map((c, w) => cell(c, r, w, top + r)));
    const grid = h(
      "div",
      {
        class: "hm",
        role: "grid",
        "aria-labelledby": "ahead-title",
        "aria-describedby": keyId,
        "aria-rowcount": nRows + 1,
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
      // the lanes are drawn for the eye; their events are in each week's label
      h("div", { class: "hm-band", "aria-hidden": "true" }, lanes(2)),
      view.rows.map((row, r) => h("div", { role: "row", class: "hm-row" }, rowHead(row, r, top + r), cells[r])),
    );
    const far = firstFar(view);
    const marks = h(
      "div",
      { class: "hm-marks", "aria-hidden": "true" },
      h("span", { class: "hm-mark-now", style: `--from:2;--to:${far + 2}` }, a.thisWeek),
      h("span", { class: "hm-mark-far", style: `--from:${far + 2}` }, a.far),
    );
    fill(scroller, h("div", { class: "hm-wrap", style: `--rows:${nRows};--weeks:${WEEKS}` }, marks, grid));
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
    const swatch = (cls, text) =>
      h("span", { class: "ah-swatch" }, h("span", { class: `hm-part ${cls}` }), h("span", {}, text));
    fill(
      legend,
      h("span", { class: "ah-legend-text" }, local.raw ? a.scaleRaw : a.scaleNormal),
      h(
        "span",
        { class: "ah-scale", "aria-hidden": "true" },
        [0, ...CUTS].map((low, i) => swatch(`s${i}`, formatCut(low, s))),
        local.year && swatch("is-year", a.parts.year),
      ),
    );
  }

  function drawNotes() {
    const key = [a.key, local.year && a.keyYear, a.typicalNote, view.anyCounts && a.countsNote];
    const caveats = [a.caveatNear, a.caveatFar, local.year && a.caveatYear];
    fill(
      notes,
      h("p", { id: keyId, class: "ah-key" }, key.filter(Boolean).join(" ")),
      h(
        "ul",
        { class: "ah-caveats" },
        caveats.filter(Boolean).map((t) => h("li", {}, t)),
      ),
    );
    fill(
      sometime,
      h("span", { class: "label" }, a.sometimeFor(view.sometime.row)),
      " ",
      view.sometime.lines.join(s.bar.sep),
    );
  }

  // ---------- the week detail ----------
  function openWeek(row, week) {
    if (!view) return;
    const same = open && open.row === row && open.week === week;
    if (!same) open = { row, week, parts: new Set() };
    for (const [r, list] of cells.entries())
      list.forEach((el, w) => el.setAttribute("aria-selected", String(r === row && w === week)));
    markOpenWeek();
    drawDetail();
    if (!same) {
      const w = view.weeks[week];
      const count = detail.querySelector(".ah-detail-count").textContent;
      announce.textContent = a.announce(view.rows[row].label, a.week(w.date, w.to), count);
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

  function gameLine(g) {
    return h(
      "li",
      {},
      h("a", { href: g.url, class: "ah-game" }, g.name),
      h("span", { class: "ah-game-meta" }, [g.date, g.followers].filter(Boolean).join(s.bar.sep)),
      g.moved && h("span", { class: "ah-moved" }, g.moved),
    );
  }

  function drawDetail() {
    if (!open) {
      fill(detail, h("p", { class: "quiet ah-hint" }, a.hint));
      return;
    }
    const w = view.weeks[open.week];
    const row = view.rows[open.row];
    const items = detailItems(numbers.weekGames(st, row.tags, w.iso, local.year), numbers.game, s);
    const parts = listParts(items, { year: local.year, open: open.parts }, s);
    const cellText = row.cells[open.week].parts.map((p) => `${a.parts[p.part]} ${p.text}`).join(s.bar.sep);
    fill(
      detail,
      h(
        "div",
        { class: "ah-detail-head" },
        h("h3", {}, a.week(w.date, w.to)),
        h("p", { class: "ah-detail-for" }, a.detailFor(row.label, s.bar[st.group])),
        h("p", { class: "ah-detail-cell" }, cellText, local.raw || row.counts ? "" : ` ${a.unitNormal}`),
      ),
      w.events.length > 0 &&
        h(
          "p",
          { class: "ah-detail-events" },
          h("span", { class: "label" }, a.detailEvents),
          " ",
          w.events
            .map((e) => `${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`)
            .join("; "),
        ),
      h(
        "p",
        { class: "ah-detail-count" },
        items.length ? a.detailCount(a.games(formatNumber(items.length, s), items.length)) : a.detailNone,
      ),
      parts.map((p) =>
        h(
          "div",
          { class: `ah-part ah-part-${p.part}` },
          h("h4", {}, p.heading),
          h("ol", { class: "ah-games" }, p.items.map(gameLine)),
          p.items.length < p.total &&
            h(
              "button",
              {
                type: "button",
                class: "ah-more",
                onclick: () => {
                  const shown = p.items.length;
                  open.parts.add(p.part);
                  drawDetail();
                  detail.querySelectorAll(`.ah-part-${p.part} .ah-game`)[shown]?.focus();
                },
              },
              a.showAll(formatNumber(p.total, s)),
            ),
        ),
      ),
    );
  }

  // ---------- drawing ----------
  function pickBand() {
    if (bandFor?.[0] === rows && bandFor[1] === events) return;
    bandFor = [rows, events];
    band = events
      ? bandEvents(events, rows[0].weeks[0], WEEKS, {
          tagNames: st.tags.map((t) => names.get(t)).filter(Boolean),
          languages: st.languages,
        })
      : { events: [], lanes: [] };
  }

  function redraw() {
    if (!body.dataset.drawn) {
      body.dataset.drawn = "true";
      fill(body, frame);
    }
    const map = numbers.heatmap(st);
    if (map !== rows) {
      // a new pick of tags, mode or languages: the open week belonged to the old rows
      open = null;
      rows = map;
    }
    pickBand();
    const hadFocus = scroller.contains(document.activeElement);
    view = buildView(rows, {
      group: st.group,
      raw: local.raw,
      year: local.year,
      mode: st.mode,
      names,
      band: band.events,
      s,
    });
    focus = {
      row: Math.min(focus.row, view.rows.length - 1),
      week: Math.min(focus.week, view.weeks.length - 1),
    };
    if (open && open.row >= view.rows.length) open = null;
    status.textContent = view.empty ?? "";
    eventsNote.textContent = events === null ? a.eventsFailed : "";
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
    // events.json's list, or null if it failed: the heatmap goes without lanes
    setEvents(list) {
      events = list;
      if (st && numbers) redraw();
    },
    // draws the selection (its numbers are computed here unless cached)
    draw(selection) {
      st = selection;
      if (numbers) redraw();
    },
    // a new selection is being computed
    busy() {
      body.setAttribute("aria-busy", "true");
    },
  };
}

// the first week faded as "dates still being set"
function firstFar(view) {
  return view.weeks.findIndex((w) => w.far);
}

function reduceMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
