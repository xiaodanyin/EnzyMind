export const residueKey = a => `${a.chain || ''}:${a.resi}:${a.icode || ''}`;
const letters = {ALA:'A',ARG:'R',ASN:'N',ASP:'D',CYS:'C',GLN:'Q',GLU:'E',GLY:'G',HIS:'H',ILE:'I',LEU:'L',LYS:'K',MET:'M',PHE:'F',PRO:'P',SER:'S',THR:'T',TRP:'W',TYR:'Y',VAL:'V'};
// A missing chain/insertion code is resolved only if the identity is unique.
export function resolveSite(site, residues, chain = '*') {
  const aa = s => letters[String(s).toUpperCase()] || String(s).toUpperCase();
  let source = residues;
  // A label-array offset is not a PDB residue number. Only link it when the
  // entire source sequence matches a complete, identically numbered chain.
  if (site.positionSource === 'sequence') {
    if (!site.sourceSequence) return null;
    const grouped = new Map();
    for (const atom of residues) {
      if (!grouped.has(atom.chain)) grouped.set(atom.chain, []);
      grouped.get(atom.chain).push(atom);
    }
    source = [...grouped.values()].filter(atoms => atoms.length === site.sourceSequence.length &&
      atoms.every((a,i) => a.resi === i+1 && !a.icode && aa(a.resn) === site.sourceSequence[i].toUpperCase())).flat();
  }
  const candidates = source.filter(a => (chain === '*' || a.chain === chain) &&
    a.resi === site.position && (!site.residue || aa(a.resn) === aa(site.residue)) &&
    (site.chain == null || a.chain === site.chain) &&
    (site.icode == null || (a.icode || '') === site.icode));
  return candidates.length === 1 ? candidates[0] : null;
}

export function placeLabels(points, width, height) {
  const placed = [];
  for (const point of points) {
    const w = Math.min(180, Math.max(82, point.text.length * 6.5 + 16)), h = 25;
    let best;
    for (const [dx, dy] of [[20,-34],[20,12],[-w-20,-34],[-w-20,12],[20,-64],[-w-20,42]]) {
      const x = Math.max(4, Math.min(width - w - 4, point.x + dx));
      const y = Math.max(4, Math.min(height - h - 4, point.y + dy));
      const overlap = placed.reduce((n,p) => n + Math.max(0, Math.min(x+w,p.x+p.w)-Math.max(x,p.x)) * Math.max(0,Math.min(y+h,p.y+p.h)-Math.max(y,p.y)), 0);
      if (!best || overlap < best.overlap) best = {x,y,w,h,overlap};
    }
    placed.push({...point, anchorX:point.x, anchorY:point.y, ...best});
  }
  return placed;
}
