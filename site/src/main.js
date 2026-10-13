// The page. A module script runs once the page is parsed (never on `load`, which
// a slow analytics script could hold back): the frame and the top bar draw at
// once, the data files load in parallel, and each part fills in when its data is in.

import "./styles.css";
import { countLine, tooFewPast } from "./count.js";
import { historyPanel, matchCount } from "./lib/heatmap.js";
import { loadData } from "./load.js";
import { query, selection } from "./state.js";
import { strings as s } from "./strings.js";
import { h } from "./ui/dom.js";
import { masthead } from "./ui/masthead.js";
import { footer, sections } from "./ui/sections.js";
import { topbar } from "./ui/topbar.js";

document.documentElement.lang = s.lang;

const bar = topbar(s, selection);
const parts = sections(s);
const foot = footer(s);

document.getElementById("app").replaceChildren(
  h("div", { class: "wrap" }, masthead(s)),
  h(
    "div",
    { class: "wrap hero" },
    h("h1", {}, s.hero.title),
    h("p", { class: "lede" }, s.hero.lede),
    h("p", { class: "caveat" }, s.hero.caveat),
  ),
  bar.el,
  h("main", { class: "wrap" }, parts.els),
  h("div", { class: "wrap" }, foot.el),
);

const data = loadData(`${import.meta.env.BASE_URL}data/`);
const reported = () => {}; // a failed file is reported once, by data.all below

data.meta.then((meta) => {
  bar.setMeta(meta);
  foot.setDate(meta.snapshot_date);
}, reported);

Promise.all([data.upcoming, data.history]).then(([games, history]) => {
  selection.subscribe((st) => {
    const q = query(st);
    const panel = historyPanel(history, q);
    bar.setCount(countLine(matchCount(games, history, q), st.group, s), tooFewPast(panel, st.group));
  });
}, reported);

data.all.then(parts.settle, (err) => {
  console.error(err);
  bar.setError();
  parts.settle();
});
