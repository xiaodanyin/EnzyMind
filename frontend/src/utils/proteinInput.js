export const UNIPROT = /^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9]\d*)?$/;
export function parseProtein(text, method = 'auto', selected = '') {
  const raw = String(text || '').trim();
  if (!raw) return { error: 'Enter a UniProt accession, paste a sequence, or upload a FASTA file.', records: [] };
  if (method === 'uniprot' || (method === 'auto' && UNIPROT.test(raw.toUpperCase()))) {
    return UNIPROT.test(raw.toUpperCase()) ? { type: 'uniprot', query: raw.toUpperCase(), records: [], label: raw.toUpperCase() } : { error: 'Enter a UniProt accession such as P00761 or A0A024RBG1.', records: [] };
  }
  const records = [];
  if (raw.startsWith('>')) {
    for (const line of raw.split(/\r?\n/)) {
      if (line.trimStart().startsWith('>')) records.push({ name: line.trimStart().slice(1).trim() || `Record ${records.length + 1}`, sequence: '' });
      else if (records.length) records.at(-1).sequence += line.replace(/\s/g, '').toUpperCase();
    }
  } else records.push({ name: 'Pasted sequence', sequence: raw.replace(/\s/g, '').toUpperCase() });
  if (records.length > 1 && (selected === '' || !records[Number(selected)])) return { error: 'This file contains multiple records. Choose one protein to analyze; sequences are never joined.', records };
  const record = records[records.length > 1 ? Number(selected) : 0];
  if (!record?.sequence) return { error: 'The selected record contains no amino acid sequence.', records };
  const invalid = [...record.sequence].map((c, i) => /[ACDEFGHIKLMNPQRSTVWY]/.test(c) ? null : `${c} at ${i + 1}`).filter(Boolean);
  if (invalid.length) return { error: `Unsupported residue(s): ${invalid.slice(0, 6).join(', ')}. These tools accept the 20 standard amino acids. Check your sequence; characters have not been removed.`, records };
  return { type: 'sequence', query: record.sequence, length: record.sequence.length, label: record.name, records };
}
export function validateChemical(value, mode) {
  const smiles = String(value || '').trim();
  if (!smiles) throw new Error(mode === 'reaction' ? 'Provide a reaction SMILES or draw a reaction.' : 'Provide a substrate SMILES or draw a molecule.');
  if (mode === 'reaction') {
    const parts = smiles.split('>');
    if (parts.length !== 3 || parts[1] || !parts[0].trim() || !parts[2].trim()) throw new Error('Use reactants>>products, with both sides of the reaction present.');
  } else if (smiles.includes('>')) throw new Error('This tool needs a substrate molecule, not a reaction.');
  return smiles;
}
