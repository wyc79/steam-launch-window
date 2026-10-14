// Children are nodes or text (never parsed as HTML); null, undefined and false
// are skipped, so `cond && h(...)` can be passed as a child. The DOM's own
// append and replaceChildren would print them as "null" or "false": use these.
export function children(...list) {
  return list.flat(Infinity).filter((c) => c != null && c !== false);
}

// h("a", { class: "x", href, onclick }, child, ...): an element.
export function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...children(kids));
  return el;
}

// el.replaceChildren with the same rule
export function fill(el, ...kids) {
  el.replaceChildren(...children(kids));
  return el;
}

// A link off this site: it opens in a new tab and says so, out of sight
// (`newTab` is the strings' newTab)
export function offsite(props, newTab, ...kids) {
  return h("a", { ...props, target: "_blank", rel: "noopener" }, ...kids, h("span", { class: "visually-hidden" }, newTab));
}

let ids = 0;
export function uid(prefix) {
  ids += 1;
  return `${prefix}-${ids}`;
}
