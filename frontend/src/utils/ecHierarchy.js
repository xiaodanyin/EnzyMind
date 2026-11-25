const pattern = /(?<![\d.])\d+\.(?:\d+|-)\.(?:\d+|-)\.(?:\d+|-)(?![\d.])/g;
export function ecNumbers(payload) {
  const found = new Set();
  function add(value) {
    if (Array.isArray(value)) value.forEach(add);
    else if (typeof value === 'string') for (const match of value.matchAll(pattern)) found.add(match[0]);
  }
  function visit(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (/^(ec|ec_number|ec_numbers)$/i.test(key)) add(child);
      else if (typeof child === 'object') visit(child);
    }
  }
  visit(payload);
  return [...found];
}
export function ecHierarchy(code, reference) {
  const parts = code.split('.');
  return ['Class', 'Subclass', 'Sub-subclass', 'Accepted enzyme name'].map((label, index) => {
    const key = parts.map((part, i) => i <= index ? part : '-').join('.');
    const unspecified = parts.slice(0, index + 1).includes('-');
    return { label, code: key, name: unspecified ? 'Not specified by this EC number' : reference?.names[key] || 'Name unavailable in this reference', known: !unspecified && Boolean(reference?.names[key]) };
  });
}
