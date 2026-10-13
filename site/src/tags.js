// Searching Steam tag names for the tag picker. Tags are meta.json rows:
// [id, name, upcoming games, past launches].

export const SHOWN = 8;

function words(name) {
  return name.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
}

// Tags whose name matches `query`, best first: the whole name, then the start of
// the name, then the start of a word ("lite" finds "Rogue-lite"), then anywhere.
// Within each, the most used tags first. An empty query lists the most used tags.
// Tags in `exclude` (ids) and tags without a name are left out.
export function searchTags(tags, query, { exclude = [], limit = SHOWN } = {}) {
  const q = query.trim().toLocaleLowerCase();
  const found = [];
  for (const tag of tags) {
    const [id, name] = tag;
    if (!name || exclude.includes(id)) continue;
    const n = name.toLocaleLowerCase();
    let rank;
    if (!q || n === q) rank = 0;
    else if (n.startsWith(q)) rank = 1;
    else if (words(n).some((w) => w.startsWith(q))) rank = 2;
    else if (n.includes(q)) rank = 3;
    else continue;
    found.push([rank, tag]);
  }
  found.sort(
    ([ra, a], [rb, b]) => ra - rb || b[2] + b[3] - (a[2] + a[3]) || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : a[0] - b[0]),
  );
  return found.slice(0, limit).map(([, tag]) => tag);
}

export function tagNames(tags) {
  return new Map(tags.map(([id, name]) => [id, name ?? String(id)]));
}
