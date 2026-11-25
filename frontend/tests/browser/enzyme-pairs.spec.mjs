import {test,expect} from './fixtures.mjs';
const rid='12345678-1234-4234-8234-123456789abc';
const sequence='A'.repeat(25);
const atoms=[];let serial=0;
for(let i=1;i<=25;i++)for(const [name,dx,element] of [['N',-.7,'N'],['CA',0,'C'],['C',.7,'C'],['O',1.1,'O']]){
 const angle=i*100*Math.PI/180;
 atoms.push(`ATOM  ${String(++serial).padStart(5)} ${name.padStart(4)} ALA A${String(i).padStart(4)}    ${(2.3*Math.cos(angle)+dx).toFixed(3).padStart(8)}${(2.3*Math.sin(angle)).toFixed(3).padStart(8)}${(i*1.5).toFixed(3).padStart(8)}  1.00 90.00          ${element.padStart(2)}`);
}
const pdb=atoms.join('\n')+'\nEND\n';
function record(overrides={}){return {id:rid,tool:'kcat',title:'Synthetic enzyme pairing fixture',status:'completed',evidence_type:'Prediction',created:1794800000,inputs:{enzyme_query:sequence,smiles:'CCO'},payload:{kcat:2.3,unit:'s^-1'},...overrides};}
async function open(page,result,{failure=false}={}){
 await page.route('**/api/workspace/**',route=>route.fulfill({json:result}));
 await page.route('**/api/query/enzyme-full-info/*/sequence',route=>route.fulfill(failure?{status:503,json:{error:'Reference sequence unavailable.'}}:{json:{success:true,requested_accession:'P00330',uniprot_id:'P00330',sequence_info:{sequence,length:25},source:{name:'Local UniProt snapshot',method:'local_snapshot',snapshot_created_at:'2026-06-14'}}}));
 await page.route('**/api/query/enzyme-full-info/*/structure',route=>route.fulfill(failure?{status:503,json:{error:'Reference model unavailable.'}}:{json:{success:true,structure_format:'pdb',structure_data:pdb,source:{kind:'predicted',version:6}}}));
 await page.goto(`/enzymind/results/${rid}`);await expect(page.locator('.enzyme-pair-result')).toBeVisible();
}

test('kinetic inputs stack at equal widths with independent heights and a plain figure control',async({page})=>{
 await open(page,record({inputs:{enzyme_query:'ACDEFGHIKLMNPQRSTVWY'.repeat(22),smiles:'[13CH3:1][C@H](O)C'}}));
 const pair=page.locator('.enzyme-pair-result');
 await expect(pair.locator('.sequence-row')).toHaveCount(10);
 await pair.getByRole('button',{name:'Next'}).click();await expect(pair.locator('.sequence-row').first()).toContainText('301');
 const enzyme=await pair.locator('.enzyme-side').boundingBox(),chemical=await pair.locator('.chemical-side').boundingBox();
 expect(Math.abs(chemical.x-enzyme.x)).toBeLessThan(1);expect(Math.abs(chemical.width-enzyme.width)).toBeLessThan(1);
 expect(chemical.y).toBeGreaterThan(enzyme.y+enzyme.height);
 await pair.locator('.chemical-preview').scrollIntoViewIfNeeded();await expect(pair.locator('.chemical-preview img')).toBeVisible({timeout:60000});
 const toolbar=pair.locator('.chemical-preview .preview-toolbar');
 expect(await toolbar.evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(0, 0, 0, 0)');
 expect(await toolbar.evaluate(el=>getComputedStyle(el).borderBottomWidth)).toBe('0px');
 const height=(await pair.locator('.chemical-side').boundingBox()).height;
 await pair.locator('.sequence-fold summary').click();
 expect((await pair.locator('.chemical-side').boundingBox()).height).toBeCloseTo(height,0);
 await pair.locator('.chemical-preview .expand-preview').click();await expect(page.getByRole('dialog')).toBeVisible();
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.locator('.result-metrics')).toHaveCount(1);await expect(pair.locator('.pair-outcome')).toContainText('2.3');
 await pair.locator('.chemical-source summary').click();await expect(pair.locator('.chemical-source pre')).toHaveText('[13CH3:1][C@H](O)C');
 await page.setViewportSize({width:390,height:844});const a=await pair.locator('.enzyme-side').boundingBox(),b=await pair.locator('.chemical-side').boundingBox();expect(b.y).toBeGreaterThan(a.y+a.height);expect(Math.abs(a.width-b.width)).toBeLessThan(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('accession-only Km uses read-only local-first reference context without starting analyses',async({page})=>{
 const requests=[];page.on('request',request=>{if(request.url().includes('/api/query/'))requests.push([request.method(),request.url()]);});
 await open(page,record({tool:'km',inputs:{enzyme_query:'P00330',smiles:'CCO'},payload:{km:0,unit:'mM'}}));
 await expect(page.locator('.sequence-preview')).toContainText('25 residues');
 await expect(page.locator('.reference-status')).toContainText('historical run was not saved');
 await expect(page.locator('.reference-status')).toContainText('Local UniProt snapshot');
 await page.locator('.reference-fold').scrollIntoViewIfNeeded();await expect(page.locator('.viewer-caption')).toBeVisible({timeout:45000});
 await expect(page.locator('.pair-outcome')).toContainText('0');await expect(page.locator('.pair-outcome')).toContainText('mM');
 expect(requests.length).toBe(2);expect(requests.every(([method])=>method==='GET')).toBe(true);
 await page.locator('.sequence-fold summary').click();await expect(page.locator('.sequence-preview')).not.toBeVisible();
});

test('stored active-site structure and reaction remain paired with source residue numbers',async({page})=>{
 await open(page,record({tool:'active-sites',inputs:{aa_sequence:sequence,rxn_smiles:'CCO>>CC=O'},payload:{data:{results:[{sequence,structure_data:pdb,active_data:[[8,'ALA','',.8,'Catalytic Site','A']]}]},result:'Saved service report'}}));
 await expect(page.locator('.enzyme-pair-result .protein-workbench')).toHaveCount(1);await expect(page.locator('.research-result .protein-workbench')).toHaveCount(1);
 await page.locator('.protein-workbench').scrollIntoViewIfNeeded();await expect(page.locator('.viewer-caption')).toBeVisible({timeout:45000});
 await page.locator('.site-table button').click();await expect(page.locator('.residue-selection')).toContainText('ALA 8');
 await expect(page.locator('.chemical-side')).toContainText('Reaction');await page.locator('.chemical-side').scrollIntoViewIfNeeded();await expect(page.locator('.chemical-preview img')).toBeVisible({timeout:60000});
 await page.locator('.sequence-fold summary').click();await expect(page.locator('.sequence-preview')).toContainText('25 residues');
});

test('EC-only recommendations pair the function hierarchy with the reaction without pretending to identify a protein',async({page})=>{
 let referenceRequests=0;page.on('request',r=>{if(r.url().includes('/enzyme-full-info/'))referenceRequests++;});
 await open(page,record({tool:'enzyme-type',inputs:{query:'CCO>>CC=O'},payload:{recommendations:[{ec_number:'1.1.1.1',confidence:27.5},{ec_number:'3.4.-.-',confidence:12.3}]}}));
 const enzyme=page.locator('.enzyme-side');await expect(enzyme).toContainText('Oxidoreductases');await expect(enzyme).toContainText('alcohol dehydrogenase');await expect(enzyme).toContainText('No individual protein sequence or structure was supplied');
 await expect(page.locator('.ec-classifications')).toHaveCount(1);await enzyme.locator('.ec-classifications summary').nth(1).click();await expect(enzyme).toContainText('Not specified by this EC number');
 await expect(enzyme.locator('.candidate-ranks')).toContainText('27.5');expect(referenceRequests).toBe(0);
});
test('active-site explanations, legend and sequence never overlap at desktop or narrow widths',async({page})=>{
 await open(page,record({tool:'active-sites',inputs:{aa_sequence:sequence,rxn_smiles:'CCO>>CC=O'},payload:{sequence,active_data:[[8,'ALA','',.8,'Catalytic Site'],[14,'ALA','',.9,'Catalytic Site'],[20,'ALA','',.7,'Binding Site']]}}));
 const viewer=page.locator('.protein-workbench');
 await expect(viewer.locator('.site-table tbody tr')).toHaveCount(3);
 for(const width of [1440,650,390]){
  await page.setViewportSize({width,height:1000});
  // Sample one frame so page-entry / scroll animations cannot skew rectangles.
  const {panel,note,legend,track}=await viewer.evaluate(el=>{
   const rect=selector=>el.querySelector(selector).getBoundingClientRect().toJSON();
   return {panel:rect('.residue-panel'),note:rect('.residue-panel .mapping-note:last-child'),legend:rect('.protein-legend'),track:rect('.sequence-section')};
  });
  expect(note.bottom).toBeLessThanOrEqual(panel.bottom+1);
  expect(legend.top).toBeGreaterThanOrEqual(note.bottom-1);
  expect(track.top).toBeGreaterThanOrEqual(legend.bottom-1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 }
});

test('reference outages preserve kinetic values, molecule, retry and source identity',async({page})=>{
 await open(page,record({tool:'km',inputs:{enzyme_query:'P00330',smiles:'CCO'},payload:{km:.74,unit:'mM'}}),{failure:true});
 await expect(page.getByRole('button',{name:'Retry reference sequence'})).toBeVisible();
 await page.locator('.reference-fold').scrollIntoViewIfNeeded();await expect(page.getByRole('button',{name:'Retry structure'})).toBeVisible();
 await expect(page.locator('.pair-outcome')).toContainText('0.74');await expect(page.locator('.enzyme-identity')).toContainText('P00330');
 await page.locator('.chemical-side').scrollIntoViewIfNeeded();await expect(page.locator('.chemical-preview img')).toBeVisible({timeout:60000});
});
test('recorded reaction notation keeps the matching EC hierarchy without inventing molecular coordinates',async({page})=>{
 await open(page,record({tool:'reaction',evidence_type:'Database annotation',inputs:{query:'1.1.1.1'},payload:{ec_number:'1.1.1.1',activities:[{ec_number:'1.1.1.1',reaction_name:'an alcohol + NAD(+) = an aldehyde + NADH + H(+)',rhea_id:'RHEA:12669'}]}}));
 await expect(page.locator('.enzyme-side')).toContainText('alcohol dehydrogenase');
 await expect(page.locator('.recorded-reaction')).toContainText('an alcohol + NAD(+) = an aldehyde + NADH + H(+)');
 await expect(page.locator('.recorded-reaction a')).toHaveAttribute('href','https://www.rhea-db.org/rhea/12669');
 await expect(page.locator('.chemical-preview')).toHaveCount(0);
});
test('legacy reaction groups keep separate residue annotations and molecular views',async({page})=>{
 await open(page,record({tool:'active-sites',inputs:{aa_sequence:sequence},payload:{results:[[0,'CCO>>CC=O',[[8,'ALA','',.8,'Catalytic Site']]],[1,'CO>>C=O',[[12,'ALA','',.7,'Binding Site']]]]}}));
 await expect(page.locator('.pair-record')).toHaveCount(2);
 await expect(page.locator('.pair-record').first().locator('.site-table')).toContainText('8');
 await expect(page.locator('.pair-record').last().locator('.site-table')).toContainText('12');
 await expect(page.locator('.pair-record').last().locator('.site-table')).not.toContainText('Catalytic Site');
 await expect(page.locator('.pair-record').first().locator('.chemical-source pre')).toHaveText('CCO>>CC=O');
 await expect(page.locator('.pair-record').last().locator('.chemical-source pre')).toHaveText('CO>>C=O');
});
