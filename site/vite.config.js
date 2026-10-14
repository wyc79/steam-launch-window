import { resolve } from "node:path";
import { defineConfig } from "vite";
import { methodsMarkdownPlugin } from "./build/methods-markdown.js";
import { strings } from "./src/strings.js";

const root = import.meta.dirname;

const escape = (text) =>
  text.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

// %SLW_TITLE% and the like in the HTML pages come from the strings file, so no
// text lives in the HTML
const pageText = {
  name: "page-text",
  transformIndexHtml: {
    order: "pre",
    handler: (html) =>
      html
        .replaceAll("%SLW_LANG%", escape(strings.lang))
        .replaceAll("%SLW_TITLE%", escape(strings.title))
        .replaceAll("%SLW_DESCRIPTION%", escape(strings.description)),
  },
};

export default defineConfig({
  base: "/steam-launch-window/",
  plugins: [pageText, methodsMarkdownPlugin(resolve(root, "../docs/methods.md"))],
  build: {
    rolldownOptions: {
      input: { main: resolve(root, "index.html"), methods: resolve(root, "methods.html") },
    },
  },
});
