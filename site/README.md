# Website

Vite and plain JavaScript. The plan is [docs/phase3-plan.md](../docs/phase3-plan.md).

```
npm ci
npm run data      # build the data files into public/data (see below)
npm run dev       # http://localhost:5173/steam-launch-window/
npm test          # unit tests and the golden cases shared with analysis/
npm run build     # into dist/; npm run preview serves it
```

`npm run preview` uses port 4173, which Windows sometimes reserves; pick any free
port with `npm run preview -- --port 5050`.

The live site is <https://wyc79.github.io/steam-launch-window/>, deployed by the `site`
workflow (`.github/workflows/site.yml`).

`npm run data` runs `python -m analysis.site_data` from the repository root on a checkout
of the data branch (`../_data` by default) and copies the branch's `site/model.json`. It
uses `$PYTHON` if set, else the repository's `.venv` when there is one, else `python`. Options:
`--data-dir <folder>`, and `--gp-dir <folder>` for follower counts (a copy of `gp/` from
the Hugging Face dataset). It reads local files only. `public/data` is gitignored.

Text lives in `src/strings.js`; the reference numbers in `src/lib/` (ports of
`analysis/heatmap.py`, `analysis/season.py` and `analysis/trends.py`).
