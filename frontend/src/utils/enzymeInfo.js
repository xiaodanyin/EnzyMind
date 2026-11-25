import { parsePdbResidues } from './resultData.js';

export const annotationColors = { 'Active site': '#148760', 'Binding site': '#dc4949' };
const letters = {ALA:'A',ARG:'R',ASN:'N',ASP:'D',CYS:'C',GLN:'Q',GLU:'E',GLY:'G',HIS:'H',ILE:'I',LEU:'L',LYS:'K',MET:'M',PHE:'F',PRO:'P',SER:'S',THR:'T',TRP:'W',TYR:'Y',VAL:'V'};
export const accessionId = value => /^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?$/.test(value || '') ? value : '';
export function annotationSites(data) {
  const sequence = data.sequence_info?.sequence || '';
  return (Array.isArray(data.functional_sites) ? data.functional_sites : []).map((site, i) => {
    const start = Number(site.start), end = Number(site.end ?? site.start);
    const exact = site.position_exact !== false && Number.isInteger(start) && start >= 1 && end === start && start <= sequence.length;
    return {...site, key:`site-${i}`, position:exact ? start : null, residue:exact ? sequence[start-1] : '',
      confidence:null, chain:null, label:site.description || site.ligand || 'No description provided',
      location:Number.isInteger(start) && start > 0 ? `${start}${end !== start ? `–${end}` : ''}${site.position_exact === false ? ' (uncertain)' : ''}` : 'Not specified'};
  });
}
// Match every coordinate to the stored UniProt sequence, including numbering.
// A new/reference sequence version must never silently relocate annotations.
export function referenceMapping(sequence, pdb) {
  const residues = parsePdbResidues(pdb || '');
  const keys = new Set(residues.map(a => `${a.chain}:${a.resi}:${a.icode}`));
  const valid = Boolean(sequence) && residues.length > 0 && keys.size === residues.length && new Set(residues.map(a=>a.chain)).size === 1 &&
    residues.every(a => Number.isInteger(a.resi) && a.resi >= 1 && a.resi <= sequence.length && !a.icode && letters[a.resn] && letters[a.resn] === sequence[a.resi-1]);
  return {valid, residues, chain:valid ? residues[0].chain : null, positions:new Set(valid ? residues.map(a=>a.resi) : [])};
}
export function kineticGroups(kinetics) {
  const groups = new Map();
  for (const [field, name] of [['km','Km'],['vmax','Vmax']]) {
    for (const [index, row] of (Array.isArray(kinetics?.[field]) ? kinetics[field] : []).entries()) {
      const key = `${name} · ${row.unit || 'unit not provided'}`;
      if (!groups.has(key)) groups.set(key, {title:key, name, unit:row.unit || 'Not provided', rows:[], original:[]});
      const group = groups.get(key), numeric = typeof row.value === 'number' || typeof row.value === 'string' && row.value.trim() !== '';
      const value = numeric && Number.isFinite(Number(row.value)) && Number(row.value) >= 0 ? Number(row.value) : null;
      group.rows.push({label:row.substrate || `Measurement ${index+1}`,value});
      group.original.push(row);
    }
  }
  return [...groups.values()];
}
