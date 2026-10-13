// The page. A module script runs once the page is parsed (never on `load`, which
// a slow analytics script could hold back): the frame and the top bar draw at
// once, the data files load in parallel, and each part fills in when its data is in.

import "./styles.css";
import { loadData } from "./load.js";
import { connect } from "./page.js";
import { selection } from "./state.js";
import { strings as s } from "./strings.js";
import { aheadSection } from "./ui/ahead.js";
import { h } from "./ui/dom.js";
import { historySection } from "./ui/history.js";
import { masthead } from "./ui/masthead.js";
import { seasonSection } from "./ui/season.js";
import { footer, sections } from "./ui/sections.js";
import { topbar } from "./ui/topbar.js";
import { trendsSection } from "./ui/trends.js";

document.documentElement.lang = s.lang;

const bar = topbar(s, selection);
const parts = sections(s);
const foot = footer(s);
const history = historySection(s, parts.bodies.history);
const season = seasonSection(s, parts.bodies.season, parts.intros.season);
const ahead = aheadSection(s, parts.bodies.ahead);
const trends = trendsSection(s, parts.bodies.trends);

document.getElementById("app").replaceChildren(
  h("div", { class: "wrap" }, masthead(s)),
  bar.summary,
  bar.el,
  h("main", { class: "wrap" }, parts.els),
  h("div", { class: "wrap" }, foot.el),
);
bar.watchSections(parts.els);

// the sticky bar's height, so a section scrolled to is not hidden under it
new ResizeObserver(([entry]) => {
  document.documentElement.style.setProperty("--bar-h", `${entry.borderBoxSize[0].blockSize}px`);
}).observe(bar.el);

connect({ data: loadData(`${import.meta.env.BASE_URL}data/`), selection, bar, parts, foot, history, season, ahead, trends, s });
