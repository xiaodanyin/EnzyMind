// Normalize scientific fields without changing units, numbering or confidence scales.
export const SITE_COLORS = {
  "Binding Site": "#dc4949",
  "Catalytic Site": "#148760",
  "Other Site": "#b48812",
};
export function unpackResult(payload) {
  let data = payload || {};
  if (data.data && typeof data.data === "object" && !Array.isArray(data.data))
    data = { ...data, ...data.data };
  if (
    data.result &&
    typeof data.result === "object" &&
    !Array.isArray(data.result)
  )
    data = { ...data, ...data.result };
  return data;
}

export function proteinPanels(payload) {
  const data = unpackResult(payload);
  const results = Array.isArray(data.results)
    ? data.results.filter(
        (r) => r && !Array.isArray(r) && typeof r === "object",
      )
    : [];
  const panels = results.length ? results : [data];
  return panels.filter(
    (p) =>
      p.structure_data ||
      p.pdb_content ||
      p.pdb_text ||
      p.active_data ||
      p.residue_labels,
  );
}

export function siteRows(data) {
  const rows = (data.active_data || [])
    .filter(Array.isArray)
    .map((site, index) => {
      const confidenceFirst =
        site[3] !== "" && site[3] != null && Number.isFinite(Number(site[3]));
      const confidence = confidenceFirst ? site[3] : site[4];
      return {
        key: String(index),
        position: Number(site[0]),
        residue: site[1],
        type: confidenceFirst ? site[4] : site[3],
        confidence:
          confidence !== "" &&
          confidence != null &&
          Number.isFinite(Number(confidence))
            ? Number(confidence)
            : null,
        chain: site[5] == null ? null : String(site[5]),
        icode: site[6] == null ? null : String(site[6]),
      };
    });
  if (!rows.length && Array.isArray(data.residue_labels)) {
    const sequence = proteinSequence(data);
    data.residue_labels.forEach((label, index) => {
      if ([1, 2, 3].includes(label))
        rows.push({
          key: String(index),
          position: index + 1,
          residue: sequence[index] || "",
          positionSource: "sequence",
          sourceSequence: sequence,
          type: ["", "Binding Site", "Catalytic Site", "Other Site"][label],
          confidence: null,
          chain: null,
          icode: null,
        });
    });
  }
  return rows.filter((r) => Number.isInteger(r.position));
}

export function proteinSequence(data) {
  if (typeof data.sequence === "string") return data.sequence;
  if (typeof data.enzyme_sequence === "string") return data.enzyme_sequence;
  if (typeof data.aa_sequence === "string") return data.aa_sequence;
  if (Array.isArray(data.enzyme_sequence_info)) {
    if (data.multi_chain || !data.enzyme_sequence_info.every(row=>Array.isArray(row) && typeof row[0]==='string')) return '';
    const display = data.enzyme_sequence_info
      .map((row) =>
        Array.isArray(row) && typeof row[0] === "string" ? row[0] : "",
      )
      .join("");
    // Older saved EasIFA records pad the final display block with '&'. Only
    // remove that suffix: stripping internal gaps would shift site numbering.
    const sequence = display.replace(/&+$/, '');
    return /^[ACDEFGHIKLMNPQRSTVWYBXZJUO]+$/i.test(sequence) ? sequence.toUpperCase() : '';
  }
  return "";
}

export function parsePdbResidues(text) {
  const residues = [],
    seen = new Set();
  const number = (value) => (value.trim() ? Number(value) : NaN);
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("ENDMDL")) break;
    if (!line.startsWith("ATOM  ") || line.slice(12, 16).trim() !== "CA")
      continue;
    if (![" ", "A", ""].includes(line[16])) continue;
    const atom = {
      chain: line.slice(21, 22).trim(),
      resi: number(line.slice(22, 26)),
      icode: line.slice(26, 27).trim(),
      resn: line.slice(17, 20).trim(),
      x: number(line.slice(30, 38)),
      y: number(line.slice(38, 46)),
      z: number(line.slice(46, 54)),
      b: number(line.slice(60, 66)),
    };
    const key = `${atom.chain}:${atom.resi}:${atom.icode}`;
    if (
      ![atom.resi, atom.x, atom.y, atom.z].every(Number.isFinite) ||
      seen.has(key)
    )
      continue;
    seen.add(key);
    residues.push(atom);
  }
  return residues;
}

// Present UI metadata in English without changing saved records or exported data.
export function evidenceLabel(record) {
  // The workspace API and historical Python records may use a localized label.
  return record.tool === "python" ? "Code calculation result" : record.evidence_type || "";
}

export function resultMetrics(record) {
  const data = unpackResult(record.payload);
  const params = data.parameters || {};
  const metrics = [];
  const add = (label, value, unit = "") => {
    // Structured measurements belong in the detailed table, not a scalar card.
    if ((typeof value === "string" && value !== "") ||
        (typeof value === "number" && Number.isFinite(value)))
      metrics.push({ label, value, unit });
  };
  if (typeof data.is_enzyme === "boolean")
    add("Classification", data.is_enzyme ? "Enzyme" : "Non-enzyme");
  if (typeof data.is_substrate === "boolean")
    add("Compatibility", data.is_substrate ? "Substrate" : "Non-substrate");
  add("EC number", data.ec_number);
  if (
    data.confidence !== null &&
    data.confidence !== undefined &&
    data.confidence !== "" &&
    Number.isFinite(Number(data.confidence))
  ) {
    const score = Number(data.confidence);
    add(
      "Model score",
      score >= 0 && score <= 1 ? (score * 100).toFixed(1) : score,
      score >= 0 && score <= 1 ? "%" : "",
    );
  }
  add("kcat", data.kcat, data.unit || "s⁻¹");
  add("Km", data.km, data.unit || "mM");
  add(
    "Sequence length",
    data.query_length ??
      data.sequence_length ??
      (record.tool === "sequence" ? data.length : undefined),
    "aa",
  );
  add("Alignment hits", data.num_results);
  add(
    "Molecular weight",
    data.molecular_weight ??
      params.molecular_weight ??
      (record.tool === "sequence" ? data.molWeight : undefined),
    "Da",
  );
  add("Isoelectric point", data.isoelectric_point ?? params.theoretical_pi);
  add("Instability index", params.instability_index);
  add("GRAVY", params.gravy);
  return metrics;
}

export function resultReference(href, origin = window.location.origin) {
  try {
    const url = new URL(href, origin);
    if (url.origin !== origin) return null;
    return (
      url.pathname.match(/^\/enzymind\/results\/([a-f0-9-]{36})\/?$/)?.[1] ||
      null
    );
  } catch {
    return null;
  }
}

export function markdownText(payload) {
  const data = unpackResult(payload);
  for (const key of ["markdown", "formatted", "result"]) {
    if (typeof data[key] === "string" && !data[key].startsWith("/tmp/"))
      return data[key];
  }
  return "";
}

export function aminoAcidComposition(payload) {
  const structured = unpackResult(payload).amino_acid_composition;
  if (Array.isArray(structured)) return structured.filter(r => r && Number.isFinite(r.count) && Number.isFinite(r.percent));
  const text = markdownText(payload);
  return [
    ...text.matchAll(/\b([A-Za-z]{3})\s+\(([A-Z])\)\s+(\d+)\s+([\d.]+)%/g),
  ].map((m) => ({
    name: m[1],
    residue: m[2],
    count: Number(m[3]),
    percent: Number(m[4]),
  }));
}
