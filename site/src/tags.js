// Searching Steam tag names for the tag picker. Tags are meta.json rows:
// [id, name, upcoming games, past launches, Simplified Chinese name or null].

import { en } from "./strings.js";

export const SHOWN = 8;

// the tag's name in the page's language (Steam's own translation), else its English name
export function tagName(tag, s = en) {
  return tag[s.tagNameAt] || tag[1];
}

function words(name) {
  return name.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
}

function rankOf(name, q) {
  const n = name.toLocaleLowerCase();
  if (!q || n === q) return 0;
  if (n.startsWith(q)) return 1;
  if (words(n).some((w) => w.startsWith(q))) return 2;
  if (n.includes(q)) return 3;
  return null;
}

// Tags whose name matches `query`, best first: the whole name, then the start of
// the name, then the start of a word ("lite" finds "Rogue-lite"), then anywhere.
// Both the page's name and the English one count, the better match deciding.
// Within each, the most used tags first. An empty query lists the most used tags.
// Tags in `exclude` (ids) and tags without a name are left out.
export function searchTags(tags, query, { exclude = [], limit = SHOWN, s = en } = {}) {
  const q = query.trim().toLocaleLowerCase();
  const found = [];
  for (const tag of tags) {
    const [id, english] = tag;
    if (!english || exclude.includes(id)) continue;
    const name = tagName(tag, s);
    const ranks = [rankOf(name, q), rankOf(english, q)].filter((r) => r !== null);
    if (!ranks.length) continue;
    found.push([Math.min(...ranks), name, tag]);
  }
  found.sort(
    ([ra, na, a], [rb, nb, b]) => ra - rb || b[2] + b[3] - (a[2] + a[3]) || (na < nb ? -1 : na > nb ? 1 : a[0] - b[0]),
  );
  return found.slice(0, limit).map(([, , tag]) => tag);
}

// id -> name in the page's language; the id stands in for a missing name
export function tagNames(tags, s = en) {
  return new Map(tags.map((tag) => [tag[0], tagName(tag, s) ?? String(tag[0])]));
}
