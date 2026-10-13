// h("a", { class: "x", href, onclick }, child, ...): an element. Children are
// nodes or text (never parsed as HTML); null and false are skipped.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

let ids = 0;
export function uid(prefix) {
  ids += 1;
  return `${prefix}-${ids}`;
}
