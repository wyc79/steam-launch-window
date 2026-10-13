// The sticky top bar: tag picker, all / any, languages, paid / free and the match
// count. It reads and writes the selection (state.js) and computes nothing itself.

import { searchTags, tagNames } from "../tags.js";
import { h, uid } from "./dom.js";

// Type to search, arrows to move, Enter to pick, Backspace on an empty field
// removes the last chip, Escape closes the list (a second Escape clears the text).
function tagPicker(s, state) {
  const listId = uid("tag-list");
  const labelId = uid("tag-label");
  const input = h("input", {
    type: "text",
    class: "tag-input",
    role: "combobox",
    "aria-autocomplete": "list",
    "aria-expanded": "false",
    "aria-controls": listId,
    "aria-labelledby": labelId,
    autocomplete: "off",
    autocapitalize: "off",
    spellcheck: "false",
    placeholder: s.bar.tagLoading,
    disabled: true,
  });
  const chips = h("ul", { class: "chips", "aria-labelledby": labelId });
  const list = h("ul", { id: listId, class: "tag-list", role: "listbox", "aria-labelledby": labelId, hidden: true });
  const field = h("div", { class: "tag-field", onclick: (e) => e.target === field && input.focus() }, chips, input);
  let tags = [];
  let names = new Map();
  let options = [];
  let active = -1;
  let quietFocus = false;

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }

  function show() {
    options = searchTags(tags, input.value, { exclude: state.get().tags });
    active = input.value.trim() && options.length ? 0 : -1;
    draw();
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function draw() {
    list.replaceChildren(
      ...(options.length
        ? options.map(([id, name, upcoming], i) =>
            h(
              "li",
              {
                id: `${listId}-${i}`,
                role: "option",
                class: "tag-option",
                "aria-selected": String(i === active),
                onmousedown: (e) => e.preventDefault(), // keep focus in the field
                onclick: () => pick(id),
              },
              h("span", {}, name),
              h("span", { class: "tag-count" }, s.bar.tagUpcoming(new Intl.NumberFormat(s.locale).format(upcoming))),
            ),
          )
        : [h("li", { role: "option", "aria-disabled": "true", class: "tag-none" }, s.bar.tagNone)]),
    );
    if (active >= 0) {
      input.setAttribute("aria-activedescendant", `${listId}-${active}`);
      list.children[active].scrollIntoView({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function pick(id) {
    state.addTag(id);
    input.value = "";
    close();
    input.focus();
  }

  function move(step) {
    if (list.hidden) show();
    if (!options.length) return;
    active = active < 0 ? (step > 0 ? 0 : options.length - 1) : (active + step + options.length) % options.length;
    draw();
  }

  input.addEventListener("input", show);
  input.addEventListener("focus", () => {
    if (!quietFocus) show();
    quietFocus = false;
  });
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") move(1);
    else if (e.key === "ArrowUp") move(-1);
    else if (e.key === "Enter") {
      const chosen = options[active] ?? (input.value.trim() ? options[0] : null);
      if (!list.hidden && chosen) pick(chosen[0]);
    } else if (e.key === "Escape") {
      if (!list.hidden) close();
      else input.value = "";
    } else if (e.key === "Backspace" && input.value === "") {
      state.removeLastTag();
      if (!list.hidden) show();
    } else return;
    e.preventDefault();
  });

  function drawChips(st) {
    chips.replaceChildren(
      ...st.tags.map((id) => {
        const name = names.get(id) ?? String(id);
        return h(
          "li",
          {},
          h(
            "button",
            {
              type: "button",
              class: "chip",
              "aria-label": s.bar.removeTag(name),
              onclick: () => {
                state.removeTag(id);
                quietFocus = true; // back to the field, without opening the list
                input.focus();
              },
            },
            h("span", {}, name),
            h("span", { class: "chip-x", "aria-hidden": "true" }, "×"),
          ),
        );
      }),
    );
    chips.hidden = !st.tags.length;
  }
  state.subscribe(drawChips);

  return {
    el: h(
      "div",
      { class: "ctl ctl-tags" },
      h("span", { class: "label", id: labelId }, s.bar.tags),
      h("div", { class: "combo" }, field, list),
    ),
    setTags(meta) {
      tags = meta.tags;
      names = tagNames(tags);
      input.disabled = false;
      input.placeholder = s.bar.tagPlaceholder;
      drawChips(state.get());
    },
  };
}

// A pair of radio buttons drawn as one switch (native radios: arrows move between them).
function switcher(s, label, key, values, state) {
  const name = uid(key);
  const inputs = values.map((v) =>
    h("input", { type: "radio", name, value: v, onchange: () => state.set({ [key]: v }) }),
  );
  state.subscribe((st) => inputs.forEach((i) => (i.checked = i.value === st[key])));
  return h(
    "fieldset",
    { class: `ctl ctl-${key}` },
    h("legend", { class: "label" }, label),
    h(
      "div",
      { class: "seg" },
      values.map((v, i) => h("label", {}, inputs[i], h("span", {}, s.bar[v]))),
    ),
  );
}

// Languages: a disclosure with a checkbox per language Steam names; none picked
// means any language.
function languagePicker(s, state) {
  const labelId = uid("lang-label");
  const current = h("span", { id: uid("lang-current") });
  const summary = h("summary", { "aria-labelledby": `${labelId} ${current.id}` }, current);
  const panel = h("div", { class: "pick-panel" });
  const details = h("details", { class: "pick" }, summary, panel);
  let boxes = [];

  const name = (code) => s.languages[code] ?? code;
  function label(langs) {
    if (!langs.length) return s.bar.anyLanguage;
    if (langs.length <= 2) return langs.map(name).join(", ");
    return s.bar.nLanguages(langs.length);
  }

  details.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && details.open) {
      details.open = false;
      summary.focus();
    }
  });
  document.addEventListener("click", (e) => {
    if (details.open && !details.contains(e.target)) details.open = false;
  });
  state.subscribe((st) => {
    current.textContent = label(st.languages);
    for (const b of boxes) b.checked = st.languages.includes(b.value);
  });

  return {
    el: h("div", { class: "ctl ctl-langs" }, h("span", { class: "label", id: labelId }, s.bar.languages), details),
    setLanguages(available) {
      const codes = Object.keys(s.languages).filter((c) => available.includes(c));
      boxes = codes.map((c) =>
        h("input", {
          type: "checkbox",
          value: c,
          checked: state.get().languages.includes(c),
          onchange: () => state.toggleLanguage(c),
        }),
      );
      panel.replaceChildren(
        h(
          "ul",
          { "aria-labelledby": labelId },
          codes.map((c, i) => h("li", {}, h("label", {}, boxes[i], h("span", {}, name(c))))),
        ),
      );
    },
  };
}

export function topbar(s, state) {
  const tags = tagPicker(s, state);
  const langs = languagePicker(s, state);
  const upcoming = h("span", { class: "count-up" });
  const past = h("span", { class: "count-past" });
  const sep = h("span", { class: "count-sep", "aria-hidden": "true" });
  const few = h("span", { class: "count-few" });
  const count = h("p", { class: "count", "aria-live": "polite" }, h("span", { class: "quiet" }, s.bar.loading));

  const el = h(
    "div",
    { class: "bar", role: "region", "aria-label": s.bar.label },
    h(
      "div",
      { class: "wrap bar-grid" },
      tags.el,
      switcher(s, s.bar.mode, "mode", ["and", "or"], state),
      langs.el,
      switcher(s, s.bar.price, "group", ["paid", "free"], state),
      count,
    ),
  );

  return {
    el,
    setMeta(meta) {
      tags.setTags(meta);
      langs.setLanguages(meta.languages);
    },
    // line: countLine's result; tooFew: past launches too few for section 03
    setCount(line, tooFew) {
      upcoming.textContent = line.upcoming;
      sep.textContent = s.bar.sep;
      past.textContent = line.past;
      few.textContent = tooFew ? ` ${s.bar.fewPast}` : "";
      count.classList.toggle("is-few", tooFew);
      count.replaceChildren(upcoming, sep, past, few);
    },
    setError() {
      const input = el.querySelector(".tag-input");
      if (input.disabled) input.placeholder = "";
      count.replaceChildren(h("span", { class: "error" }, s.bar.error));
    },
  };
}
