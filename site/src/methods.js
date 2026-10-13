// The Methods page. A placeholder until Phase 3 step 5 builds it from docs/methods.md.

import "./styles.css";
import { strings as s } from "./strings.js";
import { h } from "./ui/dom.js";
import { masthead, REPO } from "./ui/masthead.js";
import { footer } from "./ui/sections.js";

document.documentElement.lang = s.lang;
document.title = s.pageTitle(s.methods.title, s.title);

document.getElementById("app").replaceChildren(
  h("div", { class: "wrap" }, masthead(s, "methods")),
  h(
    "main",
    { class: "wrap hero" },
    h("h1", {}, s.methods.title),
    h(
      "p",
      { class: "lede" },
      s.methods.soon,
      " ",
      h("a", { href: `${REPO}/blob/main/docs/methods.md` }, s.methods.link),
    ),
    h("p", {}, h("a", { href: import.meta.env.BASE_URL }, s.methods.back)),
  ),
  h("div", { class: "wrap" }, footer(s).el),
);
