import { parseProtein, UNIPROT } from './proteinInput.js';
import { unpackResult, proteinSequence } from './resultData.js';
const proteinTools = new Set(['recognize', 'ec', 'substrate', 'kcat', 'km', 'active-sites', 'structure', 'parameters', 'blast', 'enzyme-info', 'sequence']);
const proteinFields = new Set(['uniprot_id', 'enzyme_query', 'aa_sequence', 'sequence', 'enzyme_sequence']);
const chemicalFields = new Set(['smiles', 'rxn_smiles', 'reaction_smiles', 'substrate_smiles']);
export function resultInputs(record) {
  const inputs = record.inputs && typeof record.inputs === 'object' ? record.inputs : {};
  return Object.entries(inputs).map(([key, value]) => {
    const item = { key, label: key.replaceAll('_', ' '), value: typeof value === 'string' ? value : JSON.stringify(value), kind: 'text' };
    if (typeof value !== 'string' || !value.trim()) return item;
    if (chemicalFields.has(key) || (key === 'query' && record.tool === 'enzyme-type')) {
      return { ...item, kind: 'chemical', label: value.includes('>') ? 'Reaction SMILES' : 'Substrate SMILES' };
    }
    if (proteinFields.has(key) || (key === 'query' && proteinTools.has(record.tool))) {
      const raw = value.trim();
      if (UNIPROT.test(raw.toUpperCase())) return { ...item, kind: 'accession', label: 'UniProt accession', accession: raw.toUpperCase() };
      const parsed = parseProtein(raw, 'sequence');
      // Preserve ambiguous residues and each FASTA record; no character removal
      // beyond whitespace, no concatenation of different proteins.
      if (parsed.records.length && parsed.records.every(r => /^[A-Z*.-]+$/.test(r.sequence))) return { ...item, kind: 'sequence', label: 'Protein sequence', records: parsed.records };
    }
    return item;
  });
}
export function returnedSequence(record) {
  if (!resultInputs(record).some(item => item.kind === 'accession')) return '';
  const data = unpackResult(record.payload);
  const sequence = proteinSequence(data) || (record.tool === 'sequence' && typeof data.value === 'string' ? data.value : '');
  return typeof sequence === 'string' && /^[A-Za-z\s*.-]+$/.test(sequence) ? sequence.replace(/\s/g, '').toUpperCase() : '';
}
