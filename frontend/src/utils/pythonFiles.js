// A bounded CSV preview. Cells always render as Vue text, including formulas/HTML.
export function csvPreview(text, rowLimit = 101, columnLimit = 30) {
  const rows = []; let row = [], cell = '', quoted = false;
  for (let i = 0; i < text.length && rows.length < rowLimit; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (c === ',' || c === '\n' || c === '\r')) {
      if (row.length < columnLimit) row.push(cell.slice(0, 2000));
      cell = '';
      if (c !== ',') {
        rows.push(row); row = [];
        if (c === '\r' && text[i + 1] === '\n') i++;
      }
    } else if (cell.length < 2000) cell += c;
  }
  if (rows.length < rowLimit && (cell || row.length)) {
    if (row.length < columnLimit) row.push(cell);
    rows.push(row);
  }
  return rows;
}

export function jsonPreview(value) {
  let remaining = 1000;
  function visit(item, depth = 0) {
    if (--remaining < 0 || depth > 8) return '[See full result JSON]';
    if (Array.isArray(item)) return item.slice(0, 100).map(v => visit(v, depth + 1));
    if (item && typeof item === 'object') return Object.fromEntries(Object.entries(item).slice(0, 50).map(([k, v]) => [k, visit(v, depth + 1)]));
    return typeof item === 'string' ? item.slice(0, 3000) : item;
  }
  return visit(value);
}
