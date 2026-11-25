import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceText,mcsaFigureUrl,mcsaEntryUrl,doiUrl,referenceSequence,uniprotSites,mechanismList,rolesMatrix} from '../src/utils/mcsa.js';

test('database markup becomes inert readable paragraphs without executing or fabricating links',()=>{
  assert.equal(sourceText('<p>First &amp; second.</p><p>CO<sub>2</sub><br/>Next.</p>'),'First & second.\n\nCO2\nNext.');
  assert.equal(sourceText('<script>alert(1)</script><img src=x onerror=alert(1)>Safe'),'Safe');
  assert.equal(sourceText('&lt;script&gt;alert(1)&lt;/script&gt;'),'<script>alert(1)</script>'); // interpolated as text by Vue
  assert.equal(sourceText('&#x110000;'),'&#x110000;');
});
test('only official fixed-path source diagrams and identifier-derived links are accepted',()=>{
  const path='www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_1_1';
  assert.equal(mcsaFigureUrl(path),'https://'+path);
  assert.equal(mcsaFigureUrl('http://'+path),'https://'+path);
  for(const url of ['javascript:alert(1)','https://evil.test/'+path,'https://www.ebi.ac.uk@evil.test/a','https://'+path+'?redirect=http://localhost','https://www.ebi.ac.uk/other/image.svg','data:image/svg+xml,bad'])assert.equal(mcsaFigureUrl(url),'');
  assert.equal(mcsaEntryUrl('../1'),'');assert.equal(doiUrl('javascript:alert(1)'),'');
});
test('reference sequence and residue mapping never borrow homolog sequences or PDB offsets',()=>{
  const data={basic_info:{reference_uniprot_id:'P00698'},sequence_info:{uniprot_id:'P00698',sequence:'ACDE'},active_sites_uniprot:[{uniprot_id:'P00698',code:'Cys',resid:2,roles:['nucleophile','nucleophile']},{uniprot_id:'P56868',code:'Cys',resid:2},{uniprot_id:'P00698',code:'Glu',resid:3},{uniprot_id:'P00698',code:'Asp',resid:52}],active_sites_pdb:[{pdb_id:'1dpx',code:'Asp',resid:52,auth_resid:52}]};
  assert.equal(referenceSequence(data),'ACDE');
  assert.deepEqual(uniprotSites(data).map(s=>s.position),[2,null,null,null]);
  assert.equal(referenceSequence({...data,sequence_info:{uniprot_id:'P56868',sequence:'ACDE'}}),'');
  assert.ok(uniprotSites({...data,sequence_info:null}).every(s=>s.position===null));
  assert.deepEqual(rolesMatrix(uniprotSites(data)).roles,['nucleophile']);
});
test('multiple mechanisms preserve their own references, ratings and product stages',()=>{
  const data={mechanism:{mechanisms:[{mechanism_id:1,rating:3,references:[{pubmed_id:'1'}],steps:[{step_id:5,is_product:true},{step_id:2}]},{mechanism_id:2,rating:1,references:[{pubmed_id:'2'}],summary_text:'Historical proposal.'}]}};
  const list=mechanismList(data);
  assert.deepEqual(list[0].steps.map(s=>s.step_id),[2,5]);assert.equal(list[0].steps[1].is_product,true);
  assert.equal(list[1].rating,1);assert.deepEqual(list[1].references,[{pubmed_id:'2'}]);
  assert.deepEqual(mechanismList({mechanism:null}),[]);
  assert.deepEqual(mechanismList({mechanism:{mechanism_id:1,steps:[]}})[0].references,[]);
});
