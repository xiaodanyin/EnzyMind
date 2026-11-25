import test from 'node:test';
import assert from 'node:assert/strict';
import {parseProtein,validateChemical} from '../src/utils/proteinInput.js';
import {resolveSite,residueKey,placeLabels} from '../src/utils/residueMapping.js';
import {siteRows} from '../src/utils/resultData.js';

test('FASTA requires one explicit record and never joins sequences',()=>{
 const text='>first\nACDE\n>second\nFGHI';
 const result=parseProtein(text);
 assert.match(result.error,/Choose one/);
 const selected=parseProtein(text,'auto','1');
 assert.equal(selected.query,'FGHI');
 assert.equal(selected.length,4);
});
test('normalization retains errors and distinguishes UniProt from sequence',()=>{
 assert.equal(parseProtein(' p00761 ').type,'uniprot');
 assert.equal(parseProtein('A0A024RBG1').type,'uniprot');
 assert.equal(parseProtein('ac de\nfg','sequence').query,'ACDEFG');
 assert.match(parseProtein('ACDE1*').error,/1|\*/);
 assert.ok(parseProtein('>empty\n').error);
});
test('molecules and reactions have different contracts',()=>{
 assert.equal(validateChemical('[13CH3:1][C@H](O)C','molecule'),'[13CH3:1][C@H](O)C');
 assert.throws(()=>validateChemical('CCO>>CC=O','molecule'));
 assert.throws(()=>validateChemical('CCO','reaction'));
 assert.throws(()=>validateChemical('CCO>O>CC=O','reaction'));
 assert.equal(validateChemical('CCO>>CC=O','reaction'),'CCO>>CC=O');
});
test('mapping respects chains, insertion codes and residue identity',()=>{
 const residues=[{chain:'A',resi:10,icode:'',resn:'HIS'},{chain:'B',resi:10,icode:'',resn:'HIS'},{chain:'A',resi:10,icode:'A',resn:'HIS'}];
 const site={position:10,residue:'H',chain:null,icode:null};
 assert.equal(resolveSite(site,residues),null);
 assert.equal(resolveSite({...site,chain:'A'},residues),null);
 assert.equal(residueKey(resolveSite({...site,chain:'A',icode:'A'},residues)),'A:10:A');
 assert.equal(resolveSite({...site,residue:'GLY',chain:'B'},residues),null);
 assert.equal(residueKey(resolveSite(site,residues,'B')),'B:10:');
});
test('label boxes stay in view and separate nearby labels',()=>{
 const labels=placeLabels([{x:95,y:90,text:'HIS 10 · A'},{x:95,y:90,text:'HIS 10A · A'}],300,200);
 assert.notDeepEqual([labels[0].x,labels[0].y],[labels[1].x,labels[1].y]);
 for(const l of labels){assert.ok(l.x>=0&&l.y>=0&&l.x+l.w<=300&&l.y+l.h<=200);}
});
test('sequence-indexed labels never masquerade as structure numbering',()=>{
 const residues=[{chain:'A',resi:1,icode:'',resn:'ALA'},{chain:'A',resi:2,icode:'',resn:'GLY'}];
 const [site]=siteRows({sequence:'AG',residue_labels:[0,2]});
 assert.equal(residueKey(resolveSite(site,residues)),'A:2:');
 assert.equal(resolveSite(site,residues.slice(1)),null);
 assert.equal(resolveSite(site,residues.map(a=>({...a,resi:a.resi+1}))),null);
 assert.equal(resolveSite({...site,sourceSequence:'CG'},residues),null);
 assert.equal(resolveSite(siteRows({residue_labels:[0,2]})[0],residues),null);
});
