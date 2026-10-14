// The Methods page. Vite turns docs/methods.md into this HTML at build time.

import "./styles.css";
import methodsHtml from "virtual:methods-content";
import { strings as s } from "./strings.js";
import { h } from "./ui/dom.js";
import { masthead } from "./ui/masthead.js";
import { footer } from "./ui/sections.js";

function article(html) {
  const el = h("article", { class: "methods" });
  el.innerHTML = html;
  return el;
}

export function methodsPage(text, html) {
  return [
    h("div", { class: "wrap" }, masthead(text, "methods")),
    h(
      "main",
      { class: "wrap methods-main" },
      article(html),
      h("p", { class: "methods-back" }, h("a", { href: import.meta.env.BASE_URL }, text.methods.back)),
    ),
    h("div", { class: "wrap" }, footer(text).el),
  ];
}

// A table frame is a tab stop only while its table is wider than the frame, so the
// keyboard can scroll it; a table that fits is no empty stop.
export function syncTableTabStops(root) {
  for (const frame of root.querySelectorAll(".method-table")) {
    if (frame.scrollWidth > frame.clientWidth) frame.setAttribute("tabindex", "0");
    else frame.removeAttribute("tabindex");
  }
}

export function mountMethods(doc = document) {
  doc.documentElement.lang = s.lang;
  doc.title = s.pageTitle(s.methods.title, s.title);
  doc.getElementById("app").replaceChildren(...methodsPage(s, methodsHtml));
  const body = doc.querySelector("article.methods");
  const sync = () => syncTableTabStops(body);
  sync();
  // the frame resizes with the page, the table when its text reflows
  const watch = new ResizeObserver(sync);
  for (const frame of body.querySelectorAll(".method-table")) {
    watch.observe(frame);
    if (frame.firstElementChild) watch.observe(frame.firstElementChild);
  }
}

if (typeof document !== "undefined" && document.getElementById?.("app")) mountMethods();
