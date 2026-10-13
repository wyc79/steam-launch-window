import { describe, expect, test } from "vitest";

import { renderMarkdown } from "../build/methods-markdown.js";


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

    expect(html).toContain('<div class="method-table" tabindex="0">');
    expect(html).toContain('<th scope="col" class="align-left">Left</th>');
    expect(html).toContain('<th scope="col" class="align-center">Middle</th>');
    expect(html).toContain('<td class="align-right">C</td>');
    expect(html).toContain("<tbody>");
  });

  test("renders HTTPS and local-fragment links", () => {
    const html = renderMarkdown("[Source](https://example.com/?a=1&b=2) [Trends](#trends)");

    expect(html).toContain('<a href="https://example.com/?a=1&amp;b=2">Source</a>');
    expect(html).toContain('<a href="#trends">Trends</a>');
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
});
