import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from 'node:fs';
import {
  siteRows,
  resultMetrics,
  proteinPanels,
  resultReference,
  proteinSequence,
  parsePdbResidues,
  markdownText,
  aminoAcidComposition,
} from "../src/utils/resultData.js";
import { renderMarkdown } from "../src/utils/markdown.js";
globalThis.window = { location: { origin: "https://example.org" } };
test('historical CYP2A6 display padding does not count as residues or shift sites', () => {
  const reference=JSON.parse(readFileSync(new URL('../../gateway/tests/fixtures/p11509_sequence.json',import.meta.url)));
  const rows=reference.sequence.match(/.{1,10}/g).map(chunk=>[chunk.padEnd(10,'&'),null,[]]);
  assert.equal(rows.map(row=>row[0]).join('').length,500);
  const sequence=proteinSequence({enzyme_sequence_info:rows});
  assert.equal(sequence.length,494);
  assert.equal(sequence,reference.sequence);
  assert.deepEqual([107,297,439].map(pos=>sequence[pos-1]),['F','N','C']);
  for(const invalid of ['AC&D','AC--D','AC*D']) assert.equal(proteinSequence({enzyme_sequence_info:[[invalid]]}),'');
});
test("sequence service values keep their source units and structure sequences survive normalization", () => {
  const metrics = resultMetrics({
    tool: "sequence",
    payload: { length: 231, molWeight: 24409, value: "FPTDDD" },
  });
  assert.deepEqual(metrics, [
    { label: "Sequence length", value: 231, unit: "aa" },
    { label: "Molecular weight", value: 24409, unit: "Da" },
  ]);
  assert.equal(proteinSequence({ sequence: "FVNQHL" }), "FVNQHL");
});
test("database status messages do not replace scientific fields", () => {
  assert.equal(
    markdownText({
      message: "Query successful",
      active_sites_uniprot: [{ residue: 48 }],
    }),
    "",
  );
});
test("calculated properties retain source values and composition", () => {
  const payload = {
    data: { parameters: { molecular_weight: 14313.14, theoretical_pi: 9.32 } },
    result: "- Ala (A) 12 9.3%\n- Gly (G) 12 9.3%",
  };
  assert.equal(resultMetrics({ payload })[0].value, 14313.14);
  assert.deepEqual(aminoAcidComposition(payload)[0], {
    name: "Ala",
    residue: "A",
    count: 12,
    percent: 9.3,
  });
});
test("zero and missing confidence remain distinct", () => {
  const rows = siteRows({
    active_data: [
      [57, "HIS", "#00ff00", "Catalytic Site", 0],
      [102, "ASP", "#00ff00", "Catalytic Site", null],
      [195, "SER", "#00ff00", 0.9, "Catalytic Site"],
    ],
  });
  assert.equal(rows[0].confidence, 0);
  assert.equal(rows[1].confidence, null);
  assert.equal(rows[2].confidence, 0.9);
});
test("linear kinetics are not exponentiated and zero is retained", () => {
  const metrics = resultMetrics({ payload: { kcat: 0, unit: "s^-1" } });
  assert.deepEqual(metrics, [{ label: "kcat", value: 0, unit: "s^-1" }]);
  assert.deepEqual(resultMetrics({ payload: { confidence: null } }), []);
});
test("nested EasIFA structure is available", () => {
  assert.equal(
    proteinPanels({
      result: "text",
      data: { structure_data: "ATOM", active_data: [] },
    })[0].structure_data,
    "ATOM",
  );
});
test("historical EasIFA sequence chunks retain their order", () => {
  assert.equal(
    proteinSequence({
      enzyme_sequence_info: [
        ["ACDE", 4, []],
        ["FGHI", 8, []],
      ],
    }),
    "ACDEFGHI",
  );
  assert.equal(
    proteinSequence({ aa_sequence: "MKT", enzyme_sequence_info: [] }),
    "MKT",
  );
});
test("PDB parsing preserves chains and insertion codes without inventing coordinates", () => {
  const atom = (chain, index, code = " ", alt = " ") =>
    `ATOM      1   CA${alt}ALA ${chain}${String(index).padStart(4)}${code}   ${"10.000".padStart(8)}${"20.000".padStart(8)}${"30.000".padStart(8)}  1.00 90.00           C`;
  const residues = parsePdbResidues(
    [
      atom("A", 8),
      atom("B", 8),
      atom("B", 8, "A"),
      atom("B", 8, "A", "B"),
      "ATOM      2   CA ALA A   9",
      "ENDMDL",
      atom("C", 1),
    ].join("\n"),
  );
  assert.deepEqual(
    residues.map(({ chain, resi, icode }) => [chain, resi, icode]),
    [
      ["A", 8, ""],
      ["B", 8, ""],
      ["B", 8, "A"],
    ],
  );
  assert.equal(residues[0].x, 10);
  assert.equal(residues[0].b, 90);
});
test("only same origin result links become interactive references", () => {
  const id = "d13e79a0-3112-4eef-9695-386c0b0d676e";
  assert.equal(
    resultReference(`/enzymind/results/${id}`, "https://example.org"),
    id,
  );
  assert.equal(
    resultReference(
      `https://evil.test/enzymind/results/${id}`,
      "https://example.org",
    ),
    null,
  );
});
test("model and tool Markdown cannot inject active HTML or javascript URLs", () => {
  for (const expandTables of [false, true]) {
    const html = renderMarkdown(
      "<script>alert(1)</script>\n\n[x](javascript:alert%281%29)\n\n![image](https://tracker.test/x)\n\n| Value |\n|---|\n| <img src=x onerror=alert(1)> |",
      { expandTables },
    );
    assert.ok(!html.includes("<script>"));
    assert.ok(!html.includes('href="javascript:'));
    assert.ok(!html.includes("<img"));
    assert.equal(html.includes('class="markdown-table-expand"'), expandTables);
  }
  assert.match(
    renderMarkdown("[Result](/enzymind/results/123)"),
    /href="https:\/\/example.org\/enzymind\/results\/123"/,
  );
});

test("streamed and historical Markdown never makes reserved invalid domains clickable", () => {
  for (const text of [
    "[Catalytic reactions](https://example.invalid/)",
    "[Evidence](https://SOURCE.INVALID./abc)",
    "[Evidence](//example.invalid/abc)",
    "[Evidence](https://%65xample.invalid/)",
    "[Evidence][src]\n\n[src]: https://example.invalid/",
    "<https://example.invalid/> and https://example.invalid/",
  ]) {
    assert.ok(!renderMarkdown(text).includes("<a "), text);
  }
  assert.match(renderMarkdown("[Catalytic reactions](https://example.invalid/)"), /Catalytic reactions/);
  assert.match(renderMarkdown("[UniProt](https://www.uniprot.org/uniprotkb/P00698)"), /<a href="https:\/\/www.uniprot.org/);
  assert.match(renderMarkdown("[Paper](https://example.invalid.org/)"), /<a /);
});
