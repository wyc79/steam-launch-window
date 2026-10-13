// A small stand-in for the browser DOM, enough to draw a section in Node and read
// its text. Like the real DOM, append() turns anything that is not a node into
// text, so a stray `false` shows up as "false" here too.

class Text {
  constructor(text) {
    this.data = text;
    this.parent = null;
  }
  get textContent() {
    return this.data;
  }
}

class ClassList {
  constructor(el) {
    this.el = el;
  }
  get set() {
    return new Set(this.el.className.split(/\s+/).filter(Boolean));
  }
  add(...names) {
    this.el.className = [...new Set([...this.set, ...names])].join(" ");
  }
  remove(...names) {
    this.el.className = [...this.set].filter((n) => !names.includes(n)).join(" ");
  }
  contains(name) {
    return this.set.has(name);
  }
  toggle(name, on = !this.contains(name)) {
    if (on) this.add(name);
    else this.remove(name);
  }
}

// ".a.b", "tag", '.x[data-week="3"]', and descendants (".a .b")
function matchesCompound(el, compound) {
  const tag = compound.match(/^[a-z][\w-]*/i)?.[0];
  if (tag && el.tagName !== tag.toUpperCase()) return false;
  for (const [, name] of compound.matchAll(/\.([\w-]+)/g)) if (!el.classList.contains(name)) return false;
  for (const [, k, v] of compound.matchAll(/\[([\w-]+)="([^"]*)"\]/g)) if (el.getAttribute(k) !== v) return false;
  return true;
}

function matches(el, selector) {
  const parts = selector.trim().split(/\s+/);
  if (!matchesCompound(el, parts.at(-1))) return false;
  let i = parts.length - 2;
  for (let p = el.parent; p && i >= 0; p = p.parent) if (p instanceof Element && matchesCompound(p, parts[i])) i--;
  return i < 0;
}

export class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.doc = doc;
    this.childNodes = [];
    this.parent = null;
    this.attrs = new Map();
    this.listeners = {};
    this.className = "";
    this.classList = new ClassList(this);
    this.dataset = {};
    this.hidden = false;
  }
  append(...nodes) {
    for (const n of nodes) {
      const node = n instanceof Element || n instanceof Text ? n : new Text(String(n));
      if (node.parent) node.parent.childNodes.splice(node.parent.childNodes.indexOf(node), 1);
      node.parent = this;
      this.childNodes.push(node);
    }
  }
  prepend(...nodes) {
    const old = this.childNodes.splice(0);
    this.append(...nodes);
    this.childNodes.push(...old);
  }
  replaceChildren(...nodes) {
    for (const c of this.childNodes) c.parent = null;
    this.childNodes = [];
    this.append(...nodes);
  }
  remove() {
    this.parent?.childNodes.splice(this.parent.childNodes.indexOf(this), 1);
    this.parent = null;
  }
  get children() {
    return this.childNodes.filter((c) => c instanceof Element);
  }
  get firstChild() {
    return this.childNodes[0] ?? null;
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(text) {
    this.replaceChildren(...(text ? [text] : []));
  }
  setAttribute(k, v) {
    this.attrs.set(k, String(v));
  }
  getAttribute(k) {
    return this.attrs.has(k) ? this.attrs.get(k) : null;
  }
  removeAttribute(k) {
    this.attrs.delete(k);
  }
  hasAttribute(k) {
    return this.attrs.has(k);
  }
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  // runs this element's and its ancestors' listeners, as a bubbling event would
  dispatch(type, extra = {}) {
    const event = { type, target: this, preventDefault() {}, ...extra };
    for (let el = this; el; el = el.parent) for (const fn of el.listeners[type] ?? []) fn(event);
  }
  click() {
    this.dispatch("click");
  }
  focus() {
    this.doc.activeElement = this;
    this.dispatch("focusin");
  }
  scrollIntoView() {}
  getBoundingClientRect() {
    return { width: 0, height: 0, top: 0, left: 0, bottom: 0, right: 0 };
  }
  contains(node) {
    for (let n = node; n; n = n.parent) if (n === this) return true;
    return false;
  }
  querySelectorAll(selector) {
    const out = [];
    const walk = (el) => {
      for (const c of el.children) {
        if (matches(c, selector)) out.push(c);
        walk(c);
      }
    };
    walk(this);
    return out;
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

// installs document and window on globalThis; returns the document
export function installDom() {
  const doc = {
    activeElement: null,
    createElement(tag) {
      return new Element(tag, doc);
    },
    addEventListener() {},
  };
  doc.body = doc.createElement("body");
  globalThis.document = doc;
  globalThis.window = {
    matchMedia: () => ({ matches: false, addEventListener() {} }),
  };
  return doc;
}
