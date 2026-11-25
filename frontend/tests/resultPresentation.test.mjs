import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resultInputs,returnedSequence} from '../src/utils/resultInputs.js';
import {ecNumbers,ecHierarchy} from '../src/utils/ecHierarchy.js';
import {fitAgentColumns} from '../src/utils/agentLayout.js';
import {expiryDate} from '../src/utils/retention.js';
import {alignmentBlocks,describeHit} from '../src/utils/blastAlignment.js';
import {evidenceLabel} from '../src/utils/resultData.js';

test('saved inputs distinguish reactions, sequences and accessions without altering source text',()=>{
 const query='[13CH3:1][C@H](O)C>>[13CH3:1]C(=O)C';
 assert.equal(resultInputs({tool:'enzyme-type',inputs:{query}})[0].kind,'chemical');
 const entries=resultInputs({tool:'active-sites',inputs:{aa_sequence:'>first\nacdx*\n>second\nFGHI',rxn_smiles:query}});
 assert.deepEqual(entries[0].records,[{name:'first',sequence:'ACDX*'},{name:'second',sequence:'FGHI'}]);
 assert.equal(entries[1].value,query);
 assert.equal(resultInputs({tool:'kcat',inputs:{enzyme_query:'P00761'}})[0].kind,'accession');
 assert.equal(resultInputs({tool:'unrecognized',inputs:{query:'CCO'}})[0].kind,'text');
 assert.deepEqual(resultInputs({inputs:null}),[]);
});
test('returned sequence is labelled separately and never invented for accession-only records',()=>{
 const record={tool:'recognize',inputs:{query:'P00761'},payload:{confidence:.99}};
 assert.equal(returnedSequence(record),'');
 assert.equal(returnedSequence({...record,payload:{data:{sequence:'a c\nD'}}}),'ACD');
 assert.equal(returnedSequence({...record,inputs:{query:'ACDE'},payload:{sequence:'FGHI'}}),'');
});
test('EC extraction supports multiple model labels and recommendations without matching scores',()=>{
 assert.deepEqual(ecNumbers({ec_number:'EC:3.4.21.4; 1.1.1.1',recommendations:[{ec_number:'3.4.21.4'},{ec_number:'7.1.1.2'}],confidence:0.99}),['3.4.21.4','1.1.1.1','7.1.1.2']);
 const ref={names:{'3.-.-.-':'Hydrolases','3.4.-.-':'Acting on peptide bonds (peptidases)','3.4.21.-':'Serine endopeptidases','3.4.21.4':'trypsin'}};
 assert.deepEqual(ecHierarchy('3.4.21.4',ref).map(x=>x.name),Object.values(ref.names));
 assert.match(ecHierarchy('3.4.-.-',ref)[2].name,/Not specified/);
 assert.equal(ecHierarchy('3.4.21.9999',ref)[3].known,false);
});
test('official EC reference includes all seven classes and accepted, transferred and deleted entries',()=>{
 const ref=JSON.parse(readFileSync(new URL('../src/data/ec-reference.json',import.meta.url)));
 assert.equal(ref.names['3.4.21.4'],'trypsin');
 assert.equal(ref.names['3.4.21.-'],'Serine endopeptidases');
 assert.equal(ref.names['7.-.-.-'],'Translocases');
 assert.ok(Object.values(ref.names).some(name=>name.startsWith('Transferred entry:')));
 assert.ok(Object.values(ref.names).some(name=>name.startsWith('Deleted entry')));
 assert.ok(Object.keys(ref.names).length>6000);
});
test('Agent bounds preserve chat width and clamp stale saved preferences after resizing',()=>{
 for(const width of [1150,1390,1598])for(const open of [true,false]){
  const layout=fitAgentColumns(width,open,{left:2000,right:2000});
  assert.ok(layout.left>=190&&layout.left<=400);
  assert.ok(width-layout.left-layout.right-(open?16:8)>=360);
  if(open)assert.ok(layout.right>=320);
 }
});
test('expiry date includes an English month independently of the default locale',()=>{
 assert.match(expiryDate(Date.UTC(2027,1,7,12)/1000,true),/Feb 7, 2027/);
});
test('Python evidence labels are English without mutating localized saved records',()=>{
 const record=Object.freeze({tool:'python',evidence_type:'代码计算结果'});
 assert.equal(evidenceLabel(record),'Code calculation result');
 assert.equal(record.evidence_type,'代码计算结果');
 assert.equal(evidenceLabel({tool:'python',evidence_type:'Code calculation result'}),'Code calculation result');
 assert.equal(evidenceLabel({tool:'python'}),'Code calculation result');
 for(const evidence_type of ['Prediction','Database annotation','Calculated properties']){
  assert.equal(evidenceLabel({tool:'other',evidence_type}),evidence_type);
 }
 assert.equal(evidenceLabel({tool:'other'}),'');
});

test('BLAST coordinates advance independently across gaps and preserve the midline', () => {
  const hit = {query:'A-CDV', subject:'ATCE-', match:'A C+ ', query_start:11, query_end:14, subject_start:24, subject_end:21};
  const blocks = alignmentBlocks(hit, 2);
  assert.deepEqual(blocks.map(b => [b.queryStart,b.queryEnd,b.subjectStart,b.subjectEnd]),
    [[11,11,24,23],[12,13,22,21],[14,14,null,null]]);
  assert.deepEqual(blocks.flatMap(b => b.runs.map(r => r.kind)), ['identical','gap','identical','positive','gap']);
  assert.deepEqual(blocks.flatMap(b => b.differences.map(d => [d.column,d.queryPosition,d.subjectPosition])),
    [[2,null,23],[4,13,21],[5,14,null]]);
  assert.equal(alignmentBlocks({query:'AA',subject:'AT'}, 10)[0].queryStart,null);
  assert.deepEqual(alignmentBlocks({query:'AA',subject:'A'}, 10),[]);
});

test('full-length identity distinguishes exact proteins from exact subsegments', () => {
  const hit = {title:'sp|P00330|ADH1_YEAST Alcohol dehydrogenase 1 OS=Saccharomyces cerevisiae OX=4932',
    query:'ACD', subject:'ACD', length:3, query_start:1, query_end:3};
  const full = describeHit(hit,3);
  assert.equal(full.id,'P00330'); assert.equal(full.name,'Alcohol dehydrogenase 1');
  assert.equal(full.organism,'Saccharomyces cerevisiae'); assert.equal(full.fullMatch,true);
  const short = describeHit({...hit, length:5},6);
  assert.equal(short.identity,100); assert.equal(short.coverage,50); assert.equal(short.fullMatch,false);
  const unknown = describeHit({title:'Historical hit', query_start:0, query_end:3},3);
  assert.equal(unknown.identity,null); assert.equal(unknown.coverage,null);
  assert.equal(describeHit({title:'ref|XP_123.2| Protein X [Example species]'},10).id,'XP_123.2');
});
