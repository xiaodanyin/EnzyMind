import test from 'node:test';
import assert from 'node:assert/strict';
import {enzymePairs,referenceSequenceFor} from '../src/utils/enzymePairs.js';

test('kinetic pairing preserves sequence records, molecular stereochemistry and source values',()=>{
  const record={tool:'kcat',inputs:{enzyme_query:'>first\nacdx*\n>second\nFGHI',smiles:'[13CH3:1][C@H](O)C'},payload:{kcat:2.3}};
  const frozen=JSON.stringify(record),[pair]=enzymePairs(record);
  assert.equal(pair.smiles,record.inputs.smiles);
  assert.deepEqual(pair.protein.sequences.map(s=>s.sequence),['ACDX*','FGHI']);
  assert.equal(pair.protein.ambiguousSequences,true);
  assert.equal(JSON.stringify(record),frozen);
});
test('accession-only records are reference lookups, never invented saved sequences',()=>{
  const [pair]=enzymePairs({tool:'km',inputs:{enzyme_query:'p00330',smiles:'CCO'},payload:{km:.5}});
  assert.equal(pair.protein.accession,'P00330');assert.deepEqual(pair.protein.sequences,[]);
  assert.equal(pair.protein.structure,'');
});
test('each returned protein keeps its own sequence, structure and reaction',()=>{
  const pairs=enzymePairs({tool:'active-sites',inputs:{aa_sequence:'WWWW',rxn_smiles:'CCO>>CC=O'},payload:{data:{results:[
    {sequence:'AAAA',structure_data:'PDB A',rxn_smiles:'CC>>C=C'},
    {sequence:'CCCC',pdb_content:'PDB B',rxn_smiles:'CO>>C=O'}]}}});
  assert.deepEqual(pairs.map(p=>[p.protein.sequences[0].sequence,p.protein.structure,p.smiles]),[['AAAA','PDB A','CC>>C=C'],['CCCC','PDB B','CO>>C=O']]);
});
test('different accession and unspecified multiple results do not inherit another protein',()=>{
  const [pair]=enzymePairs({tool:'substrate',inputs:{enzyme_query:'P00330',smiles:'CCO'},payload:{uniprot_id:'P00698'}});
  assert.equal(pair.protein.accession,'P00698');assert.equal(pair.protein.differentProtein,true);
  const pairs=enzymePairs({tool:'active-sites',inputs:{uniprot_id:'P00330',aa_sequence:'AAAA',rxn_smiles:'CC>>C=C'},payload:{results:[{active_data:[[1,'A','',.8,'Binding Site']]},{sequence:'CCCC'}]}});
  assert.equal(pairs[0].protein.accession,'');assert.deepEqual(pairs[0].protein.sequences,[]);
});
test('legacy active-site tuples share only their documented job-level enzyme context',()=>{
  const pairs=enzymePairs({tool:'active-sites',inputs:{aa_sequence:'AAAA'},payload:{structure_data:'SAVED PDB',results:[[0,'CC>>C=C',[[2,'A','',.8,'Catalytic Site']]],[1,'CO>>C=O',[[3,'A','',.7,'Binding Site']]]]}});
  assert.deepEqual(pairs.map(p=>p.smiles),['CC>>C=C','CO>>C=O']);
  assert.deepEqual(pairs.map(p=>p.protein.sites[0].position),[2,3]);
  assert.ok(pairs.every(p=>p.protein.sequences[0].sequence==='AAAA' && p.protein.structure==='SAVED PDB'));
});
test('EC-only enzyme inputs and recommended classes keep their hierarchy and original scores',()=>{
  assert.deepEqual(enzymePairs({tool:'km',inputs:{enzyme_query:'EC 1.1.1.1',smiles:'CCO'},payload:{}})[0].protein.ecCodes,['1.1.1.1']);
  const [pair]=enzymePairs({tool:'enzyme-type',inputs:{query:'CCO>>CC=O'},payload:{recommendations:[{ec_number:'1.1.1.1',confidence:27.5},{ec_number:'3.4.-.-',confidence:12.3}]}});
  assert.deepEqual(pair.protein.ecCodes,['1.1.1.1','3.4.-.-']);assert.equal(pair.recommendations[0].confidence,27.5);
});
test('existing specialized cards and standalone protein explorers stay independent',()=>{
  for(const tool of ['enzyme-info','mcsa-query','python'])assert.deepEqual(enzymePairs({tool,inputs:{enzyme_query:'AAAA',smiles:'CCO'}}),[]);
  assert.deepEqual(enzymePairs({tool:'active-sites',inputs:{uniprot_id:'P00330'},payload:{active_data:[]}}),[]);
});
test('recorded reaction text stays associated with its own EC and is never parsed as SMILES',()=>{
  const [pair]=enzymePairs({tool:'reaction',inputs:{query:'1.1.1.1'},payload:{ec_number:'1.1.1.1',activities:[{ec_number:'1.1.1.1',reaction_name:'an alcohol + NAD(+) = an aldehyde + NADH + H(+)'}]}});
  assert.equal(pair.smiles,'');assert.equal(pair.reactions.length,1);assert.deepEqual(pair.protein.ecCodes,['1.1.1.1']);
});
test('reference responses require exact requested identity, valid sequence and consistent length',()=>{
  const r={success:true,requested_accession:'P00330',uniprot_id:'P00330',sequence_info:{sequence:'ACDX',length:4}};
  assert.equal(referenceSequenceFor(r,'P00330'),'ACDX');
  assert.equal(referenceSequenceFor(r,'P00698'),'');
  assert.equal(referenceSequenceFor({...r,sequence_info:{sequence:'<script>',length:8}},'P00330'),'');
  assert.equal(referenceSequenceFor({...r,sequence_info:{sequence:'ACDX',length:5}},'P00330'),'');
});
