import test from 'node:test';
import assert from 'node:assert/strict';
import {accessionId,annotationSites,referenceMapping,kineticGroups} from '../src/utils/enzymeInfo.js';
const pdb = (aa='ALA',position=1,chain='A') => `ATOM      1  CA  ${aa} ${chain}${String(position).padStart(4)}      11.000  12.000  13.000  1.00 90.00           C\n`;
test('only valid accessions become model retrieval targets',()=>{
  assert.equal(accessionId('P00176'),'P00176');assert.equal(accessionId('P00330-2'),'P00330-2');
  for(const value of ['https://localhost','../P00176','P00176?url=x',null])assert.equal(accessionId(value),'');
});
test('inexact sites and ranges remain annotations without invented residue coordinates',()=>{
  const data={sequence_info:{sequence:'ACDE'},functional_sites:[{start:2,end:2},{start:1,end:3},{start:2,end:2,position_exact:false},{start:99,end:99}]};
  const sites=annotationSites(data);
  assert.equal(sites[0].residue,'C');assert.equal(sites[0].position,2);
  assert.deepEqual(sites.slice(1).map(s=>s.position),[null,null,null]);
  assert.equal(sites[1].location,'1–3');assert.match(sites[2].location,/uncertain/);
  assert.equal(annotationSites({functional_sites:[{start:2} ]})[0].position,null);
});
test('structure linking validates residue identities, numbering, chain uniqueness and coverage',()=>{
  assert.equal(referenceMapping('AC',pdb()+pdb('CYS',2)).valid,true);
  assert.equal(referenceMapping('AC',pdb('CYS',2)).valid,true); // partial coverage, original numbering
  assert.equal(referenceMapping('AC',pdb('CYS',1)).valid,false);
  assert.equal(referenceMapping('AC',pdb('ALA',2)).valid,false);
  assert.equal(referenceMapping('AC',pdb()+pdb('CYS',2,'B')).valid,false);
  assert.equal(referenceMapping('AC',pdb('UNK',99)).valid,false);
  assert.equal(referenceMapping('',pdb()).valid,false);
});
test('kinetics keep original values and separate units; missing and zero values stay distinct',()=>{
  const groups=kineticGroups({km:[{value:0,unit:'mM',substrate:'A'},{value:'2.4',unit:'mM',substrate:'B'},{value:300,unit:'uM',substrate:'C'},{value:null,unit:'mM'},{value:'< 3',unit:'mM'}]});
  assert.equal(groups.length,2);assert.deepEqual(groups[0].rows.map(r=>r.value),[0,2.4,null,null]);
  assert.equal(groups[0].original.at(-1).value,'< 3');assert.equal(groups[1].rows[0].value,300);
});
