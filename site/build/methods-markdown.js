import { readFileSync } from "node:fs";


const VIRTUAL_ID = "virtual:methods-content";
const RESOLVED_ID = `\0${VIRTUAL_ID}`;

const escapeHtml = (text) =>
  text.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

function safeHref(href) {
  return /^https?:\/\//i.test(href) || /^#[a-z0-9][\w:.-]*$/i.test(href);
}

function inline(text) {
  let html = "";
  for (let i = 0; i < text.length; ) {
    if (text[i] === "`") {
      const end = text.indexOf("`", i + 1);
      if (end >= 0) {
        html += `<code>${escapeHtml(text.slice(i + 1, end))}</code>`;
        i = end + 1;
        continue;
      }
    }
    if (text.startsWith("**", i)) {
      const end = text.indexOf("**", i + 2);
      if (end >= 0) {
        html += `<strong>${inline(text.slice(i + 2, end))}</strong>`;
        i = end + 2;
        continue;
      }
    }
    if (text[i] === "[") {
      const match = text.slice(i).match(/^\[([^\]]+)]\((\S+)\)/);
      if (match) {
        const label = inline(match[1]);
        html += safeHref(match[2]) ? `<a href="${escapeHtml(match[2])}">${label}</a>` : label;
        i += match[0].length;
        continue;
      }
    }
    html += escapeHtml(text[i]);
    i += 1;
  }
  return html;
}

function headingSlug(text) {
  return text
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/[*`]/g, "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "section";
}

// what a reader sees of inline Markdown: link labels, no emphasis or code marks
function plainText(text) {
  return text.replace(/\[([^\]]+)]\([^)]*\)/g, "$1").replace(/[*`]/g, "");
}

function cells(line) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function tableSeparator(line) {
  const parts = cells(line);
  return parts.length > 0 && parts.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function alignment(cell) {
  if (cell.startsWith(":") && cell.endsWith(":")) return "center";
  if (cell.endsWith(":")) return "right";
  return "left";
}

function startsBlock(lines, i) {
  const line = lines[i] ?? "";
  return (
    /^#{1,6}\s+/.test(line) ||
    /^\s*(?:[-*]|\d+\.)\s+/.test(line) ||
    (line.includes("|") && tableSeparator(lines[i + 1] ?? ""))
  );
}

export function renderMarkdown(markdown) {
  const lines = markdown.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
  const html = [];
  const slugs = new Map();
  let lastHeading = "";

  for (let i = 0; i < lines.length; ) {
    if (!lines[i].trim()) {
      i += 1;
      continue;
    }

    const heading = lines[i].match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (heading) {
      const level = heading[1].length;
      const base = headingSlug(heading[2]);
      const count = (slugs.get(base) ?? 0) + 1;
      slugs.set(base, count);
      const id = count === 1 ? base : `${base}-${count}`;
      html.push(`<h${level} id="${id}">${inline(heading[2])}</h${level}>`);
      lastHeading = plainText(heading[2]);
      i += 1;
      continue;
    }

    if (lines[i].includes("|") && tableSeparator(lines[i + 1] ?? "")) {
      const headings = cells(lines[i]);
      const aligns = cells(lines[i + 1]).map(alignment);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      const head = headings
        .map((cell, index) => `<th scope="col" class="align-${aligns[index] ?? "left"}">${inline(cell)}</th>`)
        .join("");
      const body = rows
        .map(
          (row) =>
            `<tr>${headings
              .map((_, index) => `<td class="align-${aligns[index] ?? "left"}">${inline(row[index] ?? "")}</td>`)
              .join("")}</tr>`,
        )
        .join("\n");
      // a frame that scrolls is a named region the keyboard can reach (src/methods.js
      // drops the tab stop while it fits)
      const label = [lastHeading, plainText(headings[0])].filter(Boolean).join(": ");
      html.push(
        `<div class="method-table" role="region" aria-label="${escapeHtml(label)}" tabindex="0">\n<table>\n<thead><tr>${head}</tr></thead>\n<tbody>${body ? `\n${body}\n` : ""}</tbody>\n</table>\n</div>`,
      );
      continue;
    }

    const item = lines[i].match(/^\s*([-*]|\d+\.)\s+(.+)/);
    if (item) {
      const ordered = /\d/.test(item[1]);
      const tag = ordered ? "ol" : "ul";
      const items = [];
      while (i < lines.length) {
        const next = lines[i].match(/^\s*([-*]|\d+\.)\s+(.+)/);
        if (!next || /\d/.test(next[1]) !== ordered) break;
        const parts = [next[2].trim()];
        i += 1;
        while (i < lines.length && lines[i].trim() && !/^\s*(?:[-*]|\d+\.)\s+/.test(lines[i])) {
          if (startsBlock(lines, i)) break;
          parts.push(lines[i].trim());
          i += 1;
        }
        items.push(parts.join(" "));
      }
      html.push(`<${tag}>\n${items.map((value) => `<li>${inline(value)}</li>`).join("\n")}\n</${tag}>`);
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !startsBlock(lines, i)) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    html.push(`<p>${inline(paragraph.join(" "))}</p>`);
  }

  return html.join("\n");
}

export function methodsMarkdownPlugin(markdownPath) {
  return {
    name: "methods-markdown",
    resolveId(id) {
      return id === VIRTUAL_ID ? RESOLVED_ID : null;
    },
    load(id) {
      if (id !== RESOLVED_ID) return null;
      this.addWatchFile(markdownPath);
      const html = renderMarkdown(readFileSync(markdownPath, "utf8"));
      return `export default ${JSON.stringify(html)};`;
    },
  };
}
