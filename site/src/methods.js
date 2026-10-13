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

export function mountMethods(doc = document) {
  doc.documentElement.lang = s.lang;
  doc.title = s.pageTitle(s.methods.title, s.title);
  doc.getElementById("app").replaceChildren(...methodsPage(s, methodsHtml));
}

if (typeof document !== "undefined" && document.getElementById?.("app")) mountMethods();
