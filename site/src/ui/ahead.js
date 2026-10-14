// Competition ahead: the heatmap (an ARIA grid of plain HTML cells, laid out by
// CSS: weeks across, or down on phones), the events lanes under the dates, and the
// week's games. Numbers come from numbers.js, text and steps from heatview.js and
// weekdetail.js, the events from events.js; this file only draws them and handles
// input.

import { formatNumber } from "../count.js";
import { bandEvents } from "../events.js";
import {
  buildView,
  countText,
  CUTS,
  eventText,
  formatCut,
  formatDate,
  formatValue,
  shownValue,
  step,
  trendLines,
} from "../heatview.js";
import { WEEKS } from "../lib/heatmap.js";
import { tagNames } from "../tags.js";
import { eventEffect } from "../eventeffects.js";
import { detailItems, findGames, listParts } from "../weekdetail.js";
import { fill, h, uid } from "./dom.js";
import { laneItems } from "./lanes.js";

const PHONE = "(max-width: 639px)";
// The niche trend line is held back (decided 2026-10-13): on today's upcoming games it
// flags about a fifth of all tags, against 4.4% on real launches, so it mostly shows
// how announced dates and developer-set tags differ from launches. It comes back once
// it can be calibrated on daily snapshots against launches (about 2027-01-10).
export const SHOW_TREND = false;

export function aheadSection(s, body) {
  const a = s.ahead;
  const phone = window.matchMedia(PHONE);
  let numbers = null;
  let names = new Map();
  let events; // undefined while loading, null if events.json failed
  let model; // model.json: undefined while loading, null if missing
  let st = null; // the selection last drawn or asked for
  let rows = null; // heatmapRows drawn (an object from the cache)
  let band = { events: [], lanes: [] };
  let bandFor = null; // [rows, events] the band was picked for
  let view = null;
  const local = { year: false }; // the raw view is the shared measure (top bar)
  const raw = () => st?.measure === "raw";
  let focus = { row: 0, week: 0 };
  let open = null; // { row, week, query: the search in its game list }
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
    h("div", { class: "ah-toggles" }, toggle(a.yearLayer, "year"), sometime),
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
  // the niche trend: lines only when a share differs clearly (heatmap.js trendFrom)
  const trend = h("div", { class: "ah-trend" });
  // a cell's raw numbers on hover or keyboard focus: one shared box, fixed to the
  // screen so the grid's scroll area cannot clip it. The cell's label holds the same
  // text, so screen readers skip the box.
  const tip = h("div", { class: "hm-tip", "aria-hidden": "true", hidden: true });
  const frame = [controls, status, trend, eventsNote, scroller, notes, detail, announce, tip];

  // ---------- the grid ----------
  // Desktop rows: 1 the dates; then, with events, the "Events" label, one row per
  // lane and a rule; then the heatmap rows. Phones put weeks in rows and the
  // heatmap rows in columns 2 on (--tc); the lanes are hidden there.
  // what past launches during a lane's event did (What history says' rules), or null
  function effectOf(e) {
    return eventEffect(model, st.group, e, { languages: st.languages }, s);
  }

  function withEffect(text, e) {
    const effect = effectOf(e);
    return effect ? `${text}. ${effect}` : text;
  }

  function weekHead(w, i) {
    const label = [a.week(w.date, w.to)];
    if (w.current) label.push(a.thisWeek);
    if (w.far) label.push(a.far);
    if (w.events.length) label.push(a.events(w.events.map((e) => withEffect(eventText(e, s), e)).join("; ")));
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
        // a mouse or pen resting on the cell; a tap goes straight to the week
        onpointerenter: (e) => e.pointerType !== "touch" && showTip(r, w),
        onpointerleave: hideTip,
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
          if (at) {
            setFocus(at.row, at.week);
            showTip(at.row, at.week);
          }
        },
        onfocusout: hideTip,
      },
      h(
        "div",
        { role: "row", class: "hm-head" },
        h("div", { role: "columnheader", class: "hm-corner" }, h("span", {}, a.corner)),
        view.weeks.map(weekHead),
      ),
      // the lanes are drawn for the eye; their events are in each week's label
      h("div", { class: "hm-band", "aria-hidden": "true" }, laneItems(band, 2, s, { note: effectOf })),
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

  let tipAt = null; // [row, week] of the cell the box is for
  function showTip(r, w) {
    const el = cells[r]?.[w];
    if (!el) return;
    tipAt = [r, w];
    tip.textContent = view.rows[r].cells[w].counts;
    tip.hidden = false;
    // above the cell, or under it when there is no room; kept inside the screen
    const cellBox = el.getBoundingClientRect();
    const box = tip.getBoundingClientRect();
    const width = window.innerWidth ?? 1024;
    const left = Math.max(8, Math.min(cellBox.left + cellBox.width / 2 - box.width / 2, width - box.width - 8));
    const above = cellBox.top - box.height - 6;
    const top = above >= 8 ? above : cellBox.bottom + 6;
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  }

  function hideTip() {
    tip.hidden = true;
    tipAt = null;
  }
  document.addEventListener("keydown", (e) => e.key === "Escape" && hideTip());
  // the box is fixed to the screen: it follows its cell when the page scrolls (a focused
  // cell scrolls itself into view)
  // (capture: also when the heatmap scrolls inside its own area)
  const follow = () => tipAt && !tip.hidden && showTip(...tipAt);
  window.addEventListener?.("scroll", follow, { passive: true, capture: true });

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
    // year-only parts change their hatch at 1.0 (dense in forced colours), so one swatch each side
    const busy = step(1);
    const one = formatCut(1, s);
    fill(
      legend,
      h("span", { class: "ah-legend-text" }, raw() ? a.scaleRaw : a.scaleNormal),
      h(
        "span",
        { class: "ah-scale", "aria-hidden": "true" },
        [0, ...CUTS].map((low, i) => swatch(`s${i}`, formatCut(low, s))),
        local.year && [
          swatch(`is-year s${busy - 1}`, a.yearUnder(one)),
          swatch(`is-year s${busy}`, a.yearFrom(one)),
        ],
      ),
    );
  }

  function drawNotes() {
    const effects = band.events.some((e) => effectOf(e)); // an event tooltip speaks of reviews
    const key = [a.key, local.year && a.keyYear, a.typicalNote, view.anyCounts && a.countsNote, effects && a.effectKey];
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
    if (!same) open = { row, week, query: "" };
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

  // "2,206 games listed: 274 with exact dates · 1,932 dated only by month or quarter
  // (together about 240 games' worth) · about 343 in a typical week."
  function listed(items, row) {
    const parts = listParts(items, { year: local.year }, s).map((p) => {
      const n = formatNumber(p.items.length, s);
      if (p.part === "exact") return a.listedExact(n);
      return (p.part === "spread" ? a.listedSpread : a.listedYear)(n, countText(p.worth, s));
    });
    parts.push(a.listedTypical(countText(row.typical, s)));
    return a.detailListed(formatNumber(items.length, s), parts.join(s.bar.sep));
  }

  // how the cell's parts add up: "0.8 + 0.7 = about 1.5 typical weeks", or in games
  // the total is the sum of the parts as shown, so the line adds up as written
  function sumText(c) {
    const games = raw() || view.rows[open.row].counts;
    const total = c.parts.reduce((sum, p) => sum + shownValue(p.value, games && p.part === "exact"), 0);
    const shown = c.parts.map((p) => p.text).join(" + ");
    return games ? a.sumRaw(shown, countText(total, s)) : a.sumNormal(shown, formatValue(total, s));
  }

  function drawDetail() {
    if (!open) {
      fill(detail, h("p", { class: "quiet ah-hint" }, a.hint));
      return;
    }
    const w = view.weeks[open.week];
    const row = view.rows[open.row];
    const items = detailItems(numbers.weekGames(st, row.tags, w.iso, local.year), numbers.game, s);
    const cellText = row.cells[open.week].parts.map((p) => `${a.parts[p.part]} ${p.text}`).join(s.bar.sep);
    // the list: a search box, a live count, and the games in a scroll area; typing
    // redraws only the list, so the box keeps its focus
    const searching = document.activeElement?.classList?.contains("ah-search");
    const listId = uid("ah-list");
    const found = h("p", { class: "ah-found", "aria-live": "polite" });
    const list = h("div", {
      id: listId,
      class: "ah-list",
      role: "region",
      tabindex: "0",
      "aria-label": a.listLabel(w.date, w.to),
    });
    const drawList = () => {
      const shown = findGames(items, open.query);
      found.textContent = a.searchCount(formatNumber(shown.length, s), formatNumber(items.length, s));
      fill(
        list,
        shown.length === 0 && h("p", { class: "quiet ah-none" }, a.noMatch),
        listParts(shown, { year: local.year }, s).map((p) =>
          h(
            "div",
            { class: `ah-part ah-part-${p.part}` },
            h("h4", {}, p.heading),
            h("ol", { class: "ah-games" }, p.items.map(gameLine)),
          ),
        ),
      );
    };
    const search = h("input", {
      type: "search",
      class: "ah-search",
      value: open.query,
      "aria-label": a.search,
      "aria-controls": listId,
      placeholder: a.search,
      autocomplete: "off",
      spellcheck: "false",
      oninput: (e) => {
        open.query = e.target.value;
        drawList();
      },
    });
    fill(
      detail,
      h(
        "div",
        { class: "ah-detail-head" },
        h("h3", {}, a.week(w.date, w.to)),
        h("p", { class: "ah-detail-for" }, a.detailFor(row.label, s.bar[st.group])),
        h("p", { class: "ah-detail-cell" }, cellText, raw() || row.counts ? "" : ` ${a.unitNormal}`),
      ),
      w.events.length > 0 &&
        h(
          "p",
          { class: "ah-detail-events" },
          h("span", { class: "label" }, a.detailEvents),
          " ",
          w.events
            .map((e) => withEffect(`${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`, e))
            .join("; "),
        ),
      h("p", { class: "ah-detail-count" }, items.length ? listed(items, row) : a.detailNone),
      items.length > 0 && h("p", { class: "ah-detail-how quiet" }, a.detailHow(sumText(row.cells[open.week]))),
      items.length > 0 && [h("div", { class: "ah-find" }, search, found), list],
    );
    if (items.length) drawList();
    if (searching) detail.querySelector(".ah-search")?.focus(); // a redraw keeps the search box in use
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
      raw: raw(),
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
    const trends = SHOW_TREND && view.empty !== a.empty ? trendLines(view.rows, numbers.trend(st), st.group, s) : [];
    fill(
      trend,
      trends.length > 0 && [
        trends.map((t) => h("p", { class: "ah-trend-line" }, t)),
        h("p", { class: "ah-trend-caveat quiet" }, s.trend.caveat),
      ],
    );
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
    // model.json, or null when it is missing: what past launches during each event did
    setModel(m) {
      model = m;
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
