import {accessionId} from './enzymeInfo.js';

const list = value => Array.isArray(value) ? value.filter(item=>item && typeof item === 'object') : [];
const letters={ALA:'A',ARG:'R',ASN:'N',ASP:'D',CYS:'C',GLN:'Q',GLU:'E',GLY:'G',HIS:'H',ILE:'I',LEU:'L',LYS:'K',MET:'M',PHE:'F',PRO:'P',SER:'S',THR:'T',TRP:'W',TYR:'Y',VAL:'V'};
export const residueLetter = code => letters[String(code || '').toUpperCase()] || (/^[ACDEFGHIKLMNPQRSTVWY]$/i.test(code || '') ? code.toUpperCase() : '');
export function sourceText(value) {
  if(typeof value !== 'string')return '';
  // Render database prose as text, never active HTML. Preserve paragraph breaks.
  const text=value.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi,'').replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/p\s*>/gi,'\n\n').replace(/<\/?[a-z][^>]*>/gi,'');
  return text.replace(/&(nbsp|amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);/gi, (entity,key)=>{
    const named={nbsp:' ',amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};
    if(!key.startsWith('#'))return named[key.toLowerCase()] || entity;
    const code=key[1].toLowerCase()==='x'?parseInt(key.slice(2),16):Number(key.slice(1));
    return code>0 && code<=0x10ffff && !(code>=0xd800 && code<=0xdfff)?String.fromCodePoint(code):entity;
  }).replace(/\n[ \t]*\n(?:\s*\n)+/g,'\n\n').trim();
}
export const mcsaEntryUrl = id => Number.isSafeInteger(Number(id)) && Number(id)>0 ? `https://www.ebi.ac.uk/thornton-srv/m-csa/entry/${Number(id)}/` : '';
export function mcsaFigureUrl(value) {
  if(typeof value!=='string')return '';
  try {
    const url=new URL(value.startsWith('www.ebi.ac.uk/') ? `https://${value}` : value);
    if(!['http:','https:'].includes(url.protocol) || url.hostname!=='www.ebi.ac.uk' || url.port || url.username || url.password || url.search || url.hash || !/^\/thornton-srv\/m-csa\/media\/schemes_svg\/[\w-]+(?:\.(?:svg|png|jpe?g))?$/.test(url.pathname))return '';
    url.protocol='https:';return url.href;
  }catch{return '';}
}
export const chebiUrl = id => /^(?:CHEBI:)?\d+$/i.test(String(id || '')) ? `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:${String(id).replace(/^CHEBI:/i,'')}` : '';
export const doiUrl = doi => /^10\.\d{4,9}\/[^\s<>]+$/.test(doi || '') ? `https://doi.org/${encodeURIComponent(doi)}` : '';
export const pdbUrl = id => /^[a-z0-9]{4}$/i.test(id || '') ? `https://www.rcsb.org/structure/${id.toUpperCase()}` : '';
export function mechanismList(data) {
  const block=data.mechanism;
  if(!block || typeof block!=='object')return [];
  return (Array.isArray(block.mechanisms) ? list(block.mechanisms) : [block]).map((mechanism,index)=>({
    ...mechanism,key:`mechanism-${index}`,steps:list(mechanism.steps).map((s,i)=>({...s,key:`step-${i}`})).sort((a,b)=>Number(a.step_id)-Number(b.step_id)),references:list(mechanism.references),
  }));
}
export function referenceSequence(data) {
  const id=accessionId(data.basic_info?.reference_uniprot_id),info=data.sequence_info;
  return id && info?.uniprot_id===id && typeof info.sequence==='string' ? info.sequence : '';
}
export function uniprotSites(data) {
  const sequence=referenceSequence(data),id=data.basic_info?.reference_uniprot_id;
  return list(data.active_sites_uniprot).map((site,index)=>{
    const residue=residueLetter(site.code);
    const position=site.uniprot_id===id && Number.isInteger(site.resid) && site.resid>0 && residue && sequence[site.resid-1]===residue ? site.resid : null;
    return {...site,key:`uniprot-${index}`,position,residue,confidence:null,chain:null,type:'M-CSA residue',
      roles:Array.isArray(site.roles)?[...new Set(site.roles.filter(r=>typeof r==='string'))].sort():[]};
  });
}
export function rolesMatrix(sites) {
  const roles=[...new Set(sites.flatMap(site=>site.roles || []))].sort();
  return {roles,rows:sites.map(site=>({key:site.key,label:`${site.code}${site.resid}`,roles:site.roles || []}))};
}
