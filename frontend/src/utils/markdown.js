import { marked } from "marked";

// The renderer only emits generated Markdown elements. Raw HTML is always text.
const escape = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const renderer = new marked.Renderer();
renderer.html = (html) => escape(html);
renderer.link = (href, title, text) => {
  try {
    const url = new URL(href, window.location.origin);
    if (!["https:", "http:"].includes(url.protocol)) return text;
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (host === 'invalid' || host.endsWith('.invalid')) {
      // Also covers streaming/older answers before final server normalization.
      return /^https?:\/\//i.test(text) ? '' : text;
    }
    const external = url.origin !== window.location.origin;
    return `<a href="${escape(url.href)}"${external ? ' target="_blank" rel="noopener noreferrer"' : ""}>${text}</a>`;
  } catch {
    return text;
  }
};
renderer.image = (_href, _title, text) => escape(text || "[Image]");
const resultRenderer = Object.assign(new marked.Renderer(), renderer);
resultRenderer.table = (header, body) => `<div class="markdown-table-preview"><button type="button" class="markdown-table-expand" aria-haspopup="dialog">Expand table</button>${renderer.table(header, body)}</div>`;
export function renderMarkdown(text, { expandTables = false } = {}) {
  return marked.parse(String(text || ""), {
    renderer: expandTables ? resultRenderer : renderer,
    gfm: true,
    breaks: true,
  });
}
