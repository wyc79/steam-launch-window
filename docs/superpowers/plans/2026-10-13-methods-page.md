# Methods Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Methods page, reviews-by-language summary, forced-colors fixes, and two-line Trends notes for Phase 3 step 5.

**Architecture:** A dependency-free Markdown renderer feeds a Vite virtual module at build time. A standard-library Python module computes language shares from the saved sample. Existing UI, strings, and CSS patterns carry the page links, responsive layout, and accessibility changes.

**Tech Stack:** Python 3.13 standard library, pytest, Vite 8, plain JavaScript ES modules, Vitest 5, CSS.

**Spec:** `docs/superpowers/specs/2026-10-13-methods-page-design.md`

## Global Constraints

- Work on branch `site-methods`, based on `origin/main`, in the existing isolated worktree.
- Add no runtime dependency and make no outside data calls.
- Treat `_data` as read-only.
- Put UI text in `site/src/strings.js` or `docs/methods.md`.
- Keep user-facing text short, plain, and free of em dashes.
- Use `C:/Users/wyc/Documents/GitHub/steam-launch-window/.venv/Scripts/python.exe` for Python.
- Use a preview port other than 4173 and stop the preview afterwards.
- End every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Open a pull request, wait for CI, and do not merge.

## Review Focus

- Markdown containing raw HTML, quotes, ampersands, or an unsafe URL must render as inert text, covered in Task 2.
- Duplicate headings must receive unique anchors and the four Methods links must land on their intended headings, covered in Tasks 2 and 3.
- Language files with missing totals, duplicate rows, bad support flags, or impossible counts must fail clearly, covered in Task 1.
- A 360px viewport must contain wide Methods tables without page-level horizontal overflow, covered in Task 3 and final browser checks.
- Windows High Contrast must retain distinguishable heatmap, history, outlook, event, and Trends marks with readable numbers, covered in Task 4.

---

### Task 1: Reviews-by-language analysis

**Files:**
- Create: `analysis/languages.py`
- Create: `tests/test_languages.py`

**Interfaces:**
- Consumes: `history/reviews_by_language.csv` and `history/language_sample_games.csv` under a local data directory.
- Produces: `summarize_languages(review_rows, sample_appids)` returning group summaries, `load_language_files(data_dir)`, and a CLI that prints a Markdown table.

- [ ] **Step 1: Write failing fixture tests**

Create tests with two small groups and literal expected pooled shares, per-game medians, and remainder. Add malformed fixtures for a duplicate `(appid, language)`, a missing `all` row, a changed support flag, a negative count, and named-language reviews greater than `all`.

```python
def test_summarize_languages_uses_pooled_totals_and_per_game_medians():
    rows = [
        {"appid": "1", "schinese_supported": "1", "language": "all", "reviews": "100"},
        {"appid": "1", "schinese_supported": "1", "language": "english", "reviews": "40"},
        {"appid": "1", "schinese_supported": "1", "language": "schinese", "reviews": "20"},
        {"appid": "2", "schinese_supported": "1", "language": "all", "reviews": "20"},
        {"appid": "2", "schinese_supported": "1", "language": "english", "reviews": "16"},
        {"appid": "2", "schinese_supported": "1", "language": "schinese", "reviews": "0"},
    ]
    got = summarize_languages(rows, {1, 2})[True]
    assert got["english"] == {"pooled": 56 / 120, "median": 0.6}
    assert got["schinese"] == {"pooled": 20 / 120, "median": 0.1}
    assert got["other"] == {"pooled": 44 / 120, "median": 0.3}
```

- [ ] **Step 2: Verify red**

Run:

```powershell
C:/Users/wyc/Documents/GitHub/steam-launch-window/.venv/Scripts/python.exe -m pytest tests/test_languages.py -q
```

Expected: collection fails because `analysis.languages` does not exist.

- [ ] **Step 3: Implement the pure calculation and CLI**

Use `csv.DictReader`, `statistics.median`, `argparse`, and `pathlib.Path`. Keep the supported language order in one tuple:

```python
LANGUAGES = (
    "english", "schinese", "tchinese", "russian", "japanese",
    "koreana", "brazilian", "german", "french", "spanish",
)
```

Calculate per-game `other` as `all - sum(LANGUAGES)`. Return unrounded floats and round only in the CLI.

- [ ] **Step 4: Verify green and run the real local files**

Run the focused tests, then:

```powershell
C:/Users/wyc/Documents/GitHub/steam-launch-window/.venv/Scripts/python.exe -m analysis.languages --data-dir C:/Users/wyc/Documents/GitHub/steam-launch-window/_data
```

Check the required English, Simplified Chinese, Russian, and Other headline values against the brief.

- [ ] **Step 5: Commit**

```powershell
git add analysis/languages.py tests/test_languages.py
git commit -m "analysis: summarize reviews by language" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Safe build-time Markdown renderer

**Files:**
- Create: `site/build/methods-markdown.js`
- Create: `site/test/methods-markdown.test.js`
- Modify: `site/vite.config.js`

**Interfaces:**
- Consumes: the UTF-8 contents of `docs/methods.md`.
- Produces: `renderMarkdown(markdown)` and virtual module `virtual:methods-content` with the rendered HTML string.

- [ ] **Step 1: Write failing renderer tests**

Cover every supported block and inline construct, duplicate heading slugs, table alignment markup, relative and HTTPS links, unsafe schemes, and raw HTML escaping.

```javascript
test("escapes raw HTML and rejects executable links", () => {
  const html = renderMarkdown("<script>x</script> [bad](javascript:alert(1))");
  expect(html).toContain("&lt;script&gt;x&lt;/script&gt;");
  expect(html).not.toContain("<script>");
  expect(html).not.toContain('href="javascript:');
});

test("gives duplicate headings unique deterministic anchors", () => {
  expect(renderMarkdown("## Trends\n\n## Trends")).toContain('id="trends-2"');
});
```

- [ ] **Step 2: Verify red**

Run `npm test -- methods-markdown.test.js` in `site/` and confirm the missing module failure.

- [ ] **Step 3: Implement the minimal renderer**

Tokenize blocks line by line. Escape text first, then recognize the small inline grammar. Wrap tables in `<div class="method-table" tabindex="0">` so only the table can scroll on phones. Generate heading IDs from lowercase ASCII words with punctuation removed and duplicate suffixes.

- [ ] **Step 4: Add the Vite virtual module**

Resolve `../docs/methods.md` from the site root, read it with `node:fs`, render it once when the virtual module loads, and export the HTML as a JSON string literal. Keep the existing page-text plugin unchanged except for composing the new plugin.

- [ ] **Step 5: Verify focused and full site tests**

Run `npm test -- methods-markdown.test.js`, then `npm test`.

- [ ] **Step 6: Commit**

```powershell
git add site/build/methods-markdown.js site/test/methods-markdown.test.js site/vite.config.js
git commit -m "site: render methods markdown at build time" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Methods content, page layout, and section links

**Files:**
- Modify: `docs/methods.md`
- Modify: `site/src/methods.js`
- Modify: `site/src/strings.js`
- Modify: `site/src/ui/sections.js`
- Modify: `site/src/styles.css`
- Create or modify: `site/test/methods.test.js`
- Modify: `site/test/sections.test.js`

**Interfaces:**
- Consumes: `virtual:methods-content` and section definitions in `strings.js`.
- Produces: a complete Methods article and four links to `methods.html#<anchor>`.

- [ ] **Step 1: Write failing page and link tests**

Assert that the Methods page renders an `article`, page title, table of contents, source links, language table, and back link. In section tests, assert these exact anchor suffixes:

```javascript
const anchors = {
  trends: "#trends",
  history: "#what-history-says",
  ahead: "#competition-ahead",
  season: "#typical-for-this-time-of-year",
};
```

- [ ] **Step 2: Verify red**

Run `npm test -- methods.test.js sections.test.js` and confirm failures for the placeholder and absent links.

- [ ] **Step 3: Rewrite `docs/methods.md` in page order**

Keep exact model facts but introduce plain-language sections for sources, the four main sections, reviews and advice, language shares, trust checks, and limits. Add the short contents list and stable heading text. Include Games Popularity permission date 2026-10-12 and the Hugging Face dataset link.

- [ ] **Step 4: Render the article in `methods.js`**

Replace the placeholder with the existing masthead, a `main` containing the imported article HTML, the back link, and the existing footer. Use a focused helper for converting the trusted build-time HTML string into the article element.

- [ ] **Step 5: Add section links and responsive Methods styles**

Put “How this is measured” in `strings.js`. Append one small link to each section intro. Style article headings, contents, code, lists, and contained table scrolling. Ensure the page grid has no width larger than its container.

- [ ] **Step 6: Verify focused and full tests plus build**

Run focused tests, `npm test`, and `npm run build`.

- [ ] **Step 7: Commit**

```powershell
git add docs/methods.md site/src/methods.js site/src/strings.js site/src/ui/sections.js site/src/styles.css site/test/methods.test.js site/test/sections.test.js
git commit -m "site: build the methods page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Forced-colors chart marks

**Files:**
- Modify: `site/test/contrast.test.js`
- Modify: `site/src/styles.css`

**Interfaces:**
- Consumes: the existing semantic classes for heatmap, history, outlook, event, and Trends marks.
- Produces: visible system-color marks under `forced-colors: active`.

- [ ] **Step 1: Extend the forced-colors tests first**

Add assertions for `.hm-part`, `.hm-part.is-year`, `.hm-block`, `.hm-tag`, `.hs-bar`, `.hs-tick`, `.ol-spread`, `.ol-bar`, and `.ol-events span`. Require `forced-color-adjust: none`, system colors, `Highlight` for selected bars, and hatching for special states.

- [ ] **Step 2: Verify red**

Run `npm test -- contrast.test.js` and confirm the new assertions fail on absent rules.

- [ ] **Step 3: Add the CSS rules**

Extend the existing forced-colors media query with `CanvasText`, `Canvas`, and `Highlight`. Preserve readable number colors. Use repeating linear gradients for year-only or recent states.

- [ ] **Step 4: Verify green and the full site suite**

Run `npm test -- contrast.test.js`, then `npm test`.

- [ ] **Step 5: Commit**

```powershell
git add site/test/contrast.test.js site/src/styles.css
git commit -m "fix: keep chart marks in forced colors" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Two-line Trends caveats

**Files:**
- Modify: `site/test/trends.test.js`
- Modify: `site/src/strings.js`
- Modify: `site/src/ui/trends.js`

**Interfaces:**
- Consumes: the existing data-derived `view.partial` line.
- Produces: exactly two non-empty `.tr-notes p` elements.

- [ ] **Step 1: Change the Trends test first**

Assert two note paragraphs, the data-derived `2026 Q4 so far: 12 of 92 days` wording for the fixture, the first-day “has just started” behavior, and the combined still-listed, launch-type, today's-tags, and no-forecast text.

- [ ] **Step 2: Verify red**

Run `npm test -- trends.test.js` and confirm the five existing paragraphs fail the new expectation.

- [ ] **Step 3: Replace the strings and note markup**

Keep `partial` and `partialStart` data-driven. Replace the four static detail strings with one second line. Render only the dynamic first paragraph and combined second paragraph.

- [ ] **Step 4: Verify focused and full tests**

Run `npm test -- trends.test.js`, then `npm test`.

- [ ] **Step 5: Commit**

```powershell
git add site/test/trends.test.js site/src/strings.js site/src/ui/trends.js
git commit -m "site: shorten trends caveats" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Documentation, data build, and final verification

**Files:**
- Modify: `docs/phase3-plan.md`
- Modify: `docs/roadmap.md`
- Create: screenshot files under an ignored verification output directory

**Interfaces:**
- Consumes: the finished branch and read-only `_data` checkout.
- Produces: updated project status, reproducible local data, screenshots, and a verified pull request.

- [ ] **Step 1: Build local site data**

From `site/`, set `PYTHON` to the repository `.venv` interpreter and run:

```powershell
$env:PYTHON='C:/Users/wyc/Documents/GitHub/steam-launch-window/.venv/Scripts/python.exe'
npm run data -- --data-dir C:/Users/wyc/Documents/GitHub/steam-launch-window/_data
```

- [ ] **Step 2: Update project status docs**

Mark Phase 3 step 5 built in `docs/phase3-plan.md`. Update the Phase 3 roadmap row and next steps without claiming later phases are complete.

- [ ] **Step 3: Run all automated verification**

Run fresh copies of `npm test`, `npm run build`, and the non-live Python suite. Record test counts and exit codes.

- [ ] **Step 4: Run browser verification**

Start `vite preview` on a free port other than 4173. Use a new headless Chrome profile per run, block non-localhost requests, and capture the main and Methods pages at 1280 and 360 pixels in light, dark, and forced-colors modes. Check keyboard use, 4.5:1 text contrast, no page-level horizontal scroll, and all four Methods anchors. Stop the preview.

- [ ] **Step 5: Commit docs**

```powershell
git add docs/phase3-plan.md docs/roadmap.md
git commit -m "docs: mark methods page built" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Review and verify the branch**

Review `git diff origin/main...HEAD`, run `git diff --check`, and compare every brief requirement with the finished files. Fix important findings with tests before continuing.

- [ ] **Step 7: Push and open the pull request**

Push `site-methods`, create the PR against `main`, include the computed language table, screenshot paths, test counts, corrected values, uncertainties, and finish the body with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Wait for CI to pass. Do not merge.
