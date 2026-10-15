// The masthead: the wyc79.github.io seal linking back to that site (as on its own
// masthead), the site name, links, and the light / dark toggle.

import { currentTheme, onThemeChange, setTheme } from "../theme.js";
import { changeLanguage } from "../language.js";
import { h, offsite } from "./dom.js";

export const HOME = "https://wyc79.github.io/";
export const REPO = "https://github.com/wyc79/steam-launch-window";

// `page` "methods" marks the Methods link as the current page
export function masthead(s, page = "tool", switchLanguage = changeLanguage) {
  const base = import.meta.env.BASE_URL;
  const currentLanguage = s.lang.startsWith("zh") ? "zh" : "en";
  const language = h(
    "button",
    {
      type: "button",
      class: "mast-toggle mast-language",
      "aria-label": s.mast.language,
      onclick: () => switchLanguage(currentLanguage === "en" ? "zh" : "en"),
    },
    h("span", { "data-opt": "en", lang: "en" }, "EN"),
    h("span", { class: "mast-slash", "aria-hidden": "true" }, "/"),
    h("span", { "data-opt": "zh", lang: "zh-CN" }, "中文"),
  );
  const opts = { light: h("span", {}, s.mast.light), dark: h("span", {}, s.mast.dark) };
  const toggle = h(
    "button",
    { type: "button", class: "mast-toggle", "aria-label": s.mast.theme },
    opts.light,
    h("span", { class: "mast-slash", "aria-hidden": "true" }, "/"),
    opts.dark,
  );
  const mark = (theme) => {
    toggle.setAttribute("aria-pressed", String(theme === "dark"));
    for (const [name, el] of Object.entries(opts)) el.classList.toggle("is-on", name === theme);
  };
  toggle.addEventListener("click", () => {
    setTheme(currentTheme() === "dark" ? "light" : "dark");
    mark(currentTheme());
  });
  onThemeChange(mark);

  return h(
    "header",
    { class: "page-head" },
    h(
      "div",
      { class: "mast" },
      h(
        "div",
        { class: "mast-brand" },
        h("a", { class: "mast-seal", href: HOME }, h("img", { src: `${base}images/wyc.png`, alt: s.mast.sealAlt })),
        // the tool page has no big title: the site name is its h1
        h(page === "tool" ? "h1" : "span", { class: "mast-title" }, h("a", { class: "mast-name", href: base }, s.mast.name)),
      ),
      h(
        "div",
        { class: "mast-links" },
        h("a", { href: `${base}methods.html`, "aria-current": page === "methods" && "page" }, s.mast.methods),
        offsite({ href: REPO }, s.newTab, s.mast.source),
      ),
      h("div", { class: "mast-utils" }, language, toggle),
    ),
    page === "tool" &&
      h(
        "div",
        { class: "mast-lede" },
        h("p", { class: "lede" }, s.mast.lede),
        h("p", { class: "caveat" }, s.mast.caveat),
      ),
  );
}
