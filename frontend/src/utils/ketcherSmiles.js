// Indigo 1.46 keeps atom maps in reactions but omits them from molecular SMILES.
// Serialize a mapped molecule through a single-reactant RXN container, without
// editing the canvas or assigning new maps. The temporary container is never
// submitted as a reaction. V3000 retains isotope, charge and stereo information.
export async function drawingSmiles(ketcher) {
  const maps = [...ketcher.editor.struct().atoms.values()].map(a=>a.aam).filter(n=>n>0);
  let smiles = (await ketcher.getSmiles(false)).trim();
  if (!maps.length || ketcher.containsReaction()) return smiles;
  const molfile = await ketcher.getMolfile('v3000');
  const converted = await ketcher.structService.convert({
    struct:`$RXN\n\nEnzyMind serialization\n\n  1  0\n$MOL\n${molfile}`,
    output_format:'chemical/x-daylight-smiles',
  }, {'smiles-saving-format':'daylight'});
  const parts = converted.struct.trim().split('>');
  if(parts.length!==3 || parts[1] || parts[2]) throw new Error('Could not preserve molecular atom maps. Your original SMILES is unchanged.');
  smiles = parts[0];
  const written = [...smiles.matchAll(/:(\d+)\]/g)].map(m=>Number(m[1])).sort((a,b)=>a-b);
  if(JSON.stringify(written)!==JSON.stringify(maps.sort((a,b)=>a-b))) throw new Error('Atom map export was incomplete. Your original SMILES is unchanged.');
  return smiles;
}
