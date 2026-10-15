import { describe, expect, test } from "vitest";

import { methodsMarkdownPlugin, renderMarkdown } from "../build/methods-markdown.js";


describe("methods Markdown", () => {
  test("renders headings, paragraphs, bold text, and inline code", () => {
    const html = renderMarkdown(`# Methods

One line
continues with **strong** text and \`p < 0.05\`.`);

    expect(html).toBe(
      '<h1 id="methods">Methods</h1>\n<p>One line continues with <strong>strong</strong> text and <code>p &lt; 0.05</code>.</p>',
    );
  });

  test("renders flat unordered and ordered lists", () => {
    const html = renderMarkdown(`- First
- Second

1. One
2. Two`);

    expect(html).toBe("<ul>\n<li>First</li>\n<li>Second</li>\n</ul>\n<ol>\n<li>One</li>\n<li>Two</li>\n</ol>");
  });

  test("renders tables with header cells and declared alignment", () => {
    const html = renderMarkdown(`| Left | Middle | Right |
|:---|:---:|---:|
| A | B | C |`);

    expect(html).toContain('<div class="method-table" role="region" aria-label="Left" tabindex="0">');
    expect(html).toContain('<th scope="col" class="align-left">Left</th>');
    expect(html).toContain('<th scope="col" class="align-center">Middle</th>');
    expect(html).toContain('<td class="align-right">C</td>');
    expect(html).toContain("<tbody>");
  });

  test("names each table frame from the heading before it and the table's first header", () => {
    const html = renderMarkdown(`## Reviews by [language](#x)

Text.

| With **Chinese** | Share |
|---|---:|
| English | 55.0% |

| Without \`Chinese\` | Share |
|---|---:|
| English | 69.4% |`);

    const labels = [...html.matchAll(/<div class="method-table" role="region" aria-label="([^"]*)" tabindex="0">/g)];
    expect(labels.map((m) => m[1])).toEqual(["Reviews by language: With Chinese", "Reviews by language: Without Chinese"]);
  });

  test("escapes a table frame's label", () => {
    const html = renderMarkdown(`### Tom & "Jerry" <b>

| A < B | C |
|---|---|
| 1 | 2 |`);

    expect(html).toContain('aria-label="Tom &amp; &quot;Jerry&quot; &lt;b&gt;: A &lt; B"');
    expect(html).not.toContain("<b>");
  });

  test("renders HTTPS links in a new tab, said out of sight, and local-fragment links in place", () => {
    const html = renderMarkdown("[Source](https://example.com/?a=1&b=2) [Trends](#trends)");

    expect(html).toContain(
      '<a href="https://example.com/?a=1&amp;b=2" target="_blank" rel="noopener">Source<span class="visually-hidden"> (opens in a new tab)</span></a>',
    );
    expect(html).toContain('<a href="#trends">Trends</a>');
  });

  test("plain HTTP links open in a new tab too", () => {
    expect(renderMarkdown("[Old](HTTP://example.com/)")).toContain('href="HTTP://example.com/" target="_blank" rel="noopener"');
  });

  test("escapes raw HTML and rejects executable links", () => {
    const html = renderMarkdown('<script>x</script> [bad](javascript:alert(1)) <img src=x onerror="x">');

    expect(html).toContain("&lt;script&gt;x&lt;/script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain('href="javascript:');
    expect(html).not.toContain("<img");
  });

  test("escapes quotes in link attributes", () => {
    const html = renderMarkdown('[safe](https://example.com/"quoted")');

    expect(html).toContain('href="https://example.com/&quot;quoted&quot;"');
  });

  test("gives duplicate headings unique deterministic anchors", () => {
    const html = renderMarkdown("## Trends\n\n## Trends\n\n## Café & Tags");

    expect(html).toContain('<h2 id="trends">Trends</h2>');
    expect(html).toContain('<h2 id="trends-2">Trends</h2>');
    expect(html).toContain('<h2 id="cafe-tags">Café &amp; Tags</h2>');
  });

  test("uses an explicit stable anchor for a translated heading", () => {
    expect(renderMarkdown("## 趋势 {#trends}")).toBe('<h2 id="trends">趋势</h2>');
  });

  test("exposes a separate virtual article for Chinese", () => {
    const plugin = methodsMarkdownPlugin({ en: "methods.md", zh: "methods.zh.md" });
    expect(plugin.resolveId("virtual:methods-content")).not.toBeNull();
    expect(plugin.resolveId("virtual:methods-content-zh")).not.toBeNull();
  });
});
