// The numbered sections and the footer. Each section has a body that step 4
// fills (heatmap, outlook, history panel, trends); until the data is in it says so. A
// section that draws itself marks its body `data-drawn`.

import { REPO } from "./masthead.js";
import { h } from "./dom.js";

// page order; the numbers (01, 02, ...) follow it
export const SECTIONS = ["trends", "history", "ahead", "season"];

export function sectionNumber(key) {
  return String(SECTIONS.indexOf(key) + 1).padStart(2, "0");
}

export function sections(s) {
  const bodies = {};
  const intros = {};
  const els = SECTIONS.map((key) => {
    const { title, intro } = s.sections[key];
    const num = sectionNumber(key);
    const titleId = `${key}-title`;
    intros[key] = h("p", { class: "intro" }, intro);
    bodies[key] = h("div", { class: "section-body", "aria-busy": "true" }, h("p", { class: "quiet" }, s.bar.loading));
    return h(
      "section",
      { id: key, class: "page-section", "data-index": num, "aria-labelledby": titleId },
      h("h2", { id: titleId }, title),
      intros[key],
      bodies[key],
    );
  });
  return {
    els,
    bodies,
    intros, // a section may fill in its intro (Typical for this time of year names the group)
    // the data is in (or failed, which the top bar reports): drop the loading line
    // of each section that has not drawn itself yet
    settle() {
      for (const body of Object.values(bodies)) {
        if (body.dataset.drawn) continue;
        body.removeAttribute("aria-busy");
        body.replaceChildren();
      }
    },
  };
}

const LINKS = {
  steam: "https://store.steampowered.com/",
  gp: "https://games-popularity.com/",
  hf: "https://huggingface.co/datasets/strikeoo/steam-launch-data",
};

export function footer(s) {
  const f = s.footer;
  const asOf = h("span");
  const link = (href, text) => h("a", { href }, text);
  const el = h(
    "footer",
    { class: "page-foot" },
    h(
      "p",
      { class: "foot-credits" },
      h("span", { class: "label" }, f.data),
      link(LINKS.steam, f.steam),
      f.steamNote,
      s.bar.sep,
      link(LINKS.gp, f.gp),
      f.gpNote,
      s.bar.sep,
      link(LINKS.hf, f.hf),
      f.hfNote,
      asOf,
    ),
    h(
      "p",
      { class: "foot-links" },
      link(`${import.meta.env.BASE_URL}methods.html`, f.methods),
      s.bar.sep,
      link(REPO, f.source),
      s.bar.sep,
      h("span", {}, f.affiliation),
    ),
  );
  return {
    el,
    setDate(date) {
      asOf.textContent = f.asOf(date);
    },
  };
}
