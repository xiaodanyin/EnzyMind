import {resultInputs} from './resultInputs.js';
import {unpackResult,proteinSequence,siteRows} from './resultData.js';
import {ecNumbers} from './ecHierarchy.js';
import {accessionId} from './enzymeInfo.js';

const pairTools = new Set(['kcat','km','substrate','active-sites','enzyme-type']);
const excluded = new Set(['python','enzyme-info','mcsa-query']);
export const cleanProteinSequence = value => typeof value === 'string' && /^[A-Za-z\s*.-]+$/.test(value) ? value.replace(/\s/g,'').toUpperCase() : '';
const structureText = data => [data?.structure_data,data?.pdb_content,data?.pdb_text].find(v=>typeof v==='string' && v.trim()) || '';
const chemical = data => ['rxn_smiles','reaction_smiles','substrate_smiles','smiles'].map(k=>data?.[k]).find(v=>typeof v==='string' && v.trim()) || '';
const accession = value => accessionId(typeof value==='string' ? value.trim().toUpperCase() : '');
function queryEC(inputs) {
  return ['enzyme_query','query'].flatMap(key=>typeof inputs[key]==='string' && /^(?:EC\s*:?\s*)?\d+\.(?:\d+|-)\.(?:\d+|-)\.(?:\d+|-)$/i.test(inputs[key].trim()) ? ecNumbers({ec:inputs[key]}) : []);
}

// Only combine fields saved for the same record / returned row. Never join
// other workspace results by list order or substitute a homolog's sequence.
export function enzymePairs(record) {
  if(excluded.has(record.tool))return [];
  const data=unpackResult(record.payload),inputs=record.inputs || {},items=resultInputs(record);
  const inputChem=items.find(i=>i.kind==='chemical')?.value || '';
  const inputAcc=items.find(i=>i.kind==='accession')?.accession || (record.tool==='reaction' ? accession(inputs.query) : '');
  const inputSequences=items.filter(i=>i.kind==='sequence').flatMap(i=>i.records.map(r=>({...r,source:'Submitted sequence'})));
  const legacyContext=Object.fromEntries(['uniprot_id','sequence','enzyme_sequence','aa_sequence','enzyme_sequence_info','structure_data','pdb_content','pdb_text','structure_format','confidence_type'].filter(k=>data[k]!=null).map(k=>[k,data[k]]));
  const legacyRows=new WeakSet();
  const rows=Array.isArray(data.results) && data.results.length ? data.results.map(r=>{
    if(record.tool==='active-sites' && Array.isArray(r) && typeof r[1]==='string' && Array.isArray(r[2])){
      const row={...legacyContext,rxn_smiles:r[1],active_data:r[2]};legacyRows.add(row);return row;
    }
    return r;
  }).filter(r=>r && typeof r==='object' && !Array.isArray(r)) : [data];
  const inputCodes=[...ecNumbers(inputs),...queryEC(inputs)];
  return rows.map((row,index)=>{
    const ownAcc=accession(row.uniprot_id || row.accession),differentProtein=Boolean(ownAcc && inputAcc && ownAcc!==inputAcc);
    const commonInput=rows.length===1 || legacyRows.has(row);
    const id=ownAcc || (commonInput ? inputAcc : '');
    const returned=cleanProteinSequence(proteinSequence(row) || row.sequence_info?.sequence);
    const sequences=returned ? [{name:'Sequence saved with this result',sequence:returned,source:'Returned sequence'}] :
      !differentProtein && commonInput ? inputSequences : [];
    const ownChem=chemical(row),smiles=ownChem || inputChem;
    const reactions=Array.isArray(row.activities) ? row.activities.filter(r=>r && typeof r.reaction_name==='string' && r.reaction_name.trim()) : [];
    const codes=[...new Set([...(!differentProtein ? inputCodes : []),...ecNumbers(row)])];
    const structure=structureText(row) || (!differentProtein && commonInput ? structureText(inputs) : '');
    const hasProtein=id || sequences.length || structure || codes.length || siteRows(row).length;
    if(!pairTools.has(record.tool) && !((smiles || reactions.length) && hasProtein))return null;
    // Active-site queries without any chemical context retain the existing
    // full-width structure explorer rather than suggesting an unknown reaction.
    if(record.tool==='active-sites' && !smiles)return null;
    const isReaction=Boolean(reactions.length || smiles.includes('>') || row.rxn_smiles || row.reaction_smiles || inputs.rxn_smiles || inputs.reaction_smiles || record.tool==='enzyme-type');
    return {key:`${record.id || record.tool}-${index}`,smiles,reactions,isReaction,chemicalSource:ownChem || reactions.length ? 'Returned with this result' : 'Submitted with this run',
      protein:{accession:id,sequences,structure,format:row.structure_format || inputs.structure_format || 'pdb',sites:siteRows(row),
        ecCodes:codes,confidenceType:row.confidence_type || '',name:row.name || row.protein_name || '',
        compatibility:row.record_compatibility?.message || '',differentProtein,
        ambiguousSequences:sequences.length>1},recommendations:record.tool==='enzyme-type' ? row.recommendations || [] : []};
  }).filter(Boolean);
}

export function referenceSequenceFor(result, requested) {
  if(!result?.success || result.requested_accession!==requested || !accession(result.uniprot_id))return '';
  const sequence=cleanProteinSequence(result.sequence_info?.sequence);
  return result.sequence_info?.length===sequence.length ? sequence : '';
}
