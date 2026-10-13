// Reading the site's data files (analysis/site_data.py writes them).

// Rows of upcoming.json or history.json as objects; with `meta`, tags and langs
// are turned back into tag ids and language names (site_data.load_table).
export function fromTable(table, meta = null) {
  const rows = table.rows.map((r) => Object.fromEntries(table.columns.map((c, i) => [c, r[i]])));
  if (meta) {
    for (const r of rows) {
      r.tags = r.tags.map((i) => meta.tags[i][0]);
      r.langs = r.langs.map((i) => meta.languages[i]);
    }
  }
  return rows;
}
