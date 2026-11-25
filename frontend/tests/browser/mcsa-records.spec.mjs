import {test,expect} from './fixtures.mjs';
const rid='12345678-1234-4234-8234-123456789abc';
const sequence='A'.repeat(25);
const figure='www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/macie_entry_1_1_1';
const payload={found:true,basic_info:{mcsa_id:1,enzyme_name:'Synthetic M-CSA test record',reference_uniprot_id:'P56868',ec_numbers:['5.1.1.3'],description:'<p>First paragraph.</p><p>Second paragraph.</p>'},
 sequence_info:{uniprot_id:'P56868',sequence},reaction:{reactants:[{name:'Test reactant',count:2,chebi_id:'29985',smiles:'CCO'}],products:[{name:'Test product',count:1,smiles:'CC=O'}]},
 active_sites_uniprot:[{uniprot_id:'P56868',code:'Ala',resid:8,is_reference:true,roles:['proton donor'],main_annotation:'Synthetic role annotation.'}],
 active_sites_pdb:[{pdb_id:'1b73',chain:'A',code:'Ala',resid:52,auth_resid:35,is_reference:true,roles:['proton donor']}],
 mechanism:{mechanisms:[{mechanism_id:1,rating:3,summary_text:'First source proposal.',steps:[{step_id:1,description:'First source step.',figure},{step_id:5,description:'Products',is_product:true,figure}],references:[{pubmed_id:'111',title:'First source reference',evidence_types:['Test evidence']}]},{mechanism_id:2,rating:1,summary_text:'Historical proposal retained as recorded.',steps:[],references:[{pubmed_id:'222',title:'Second source reference'}]}]},cofactors:[]};
const atoms=[];let serial=0;
for(let i=1;i<=25;i++)for(const [name,dx,element] of [['N',-.7,'N'],['CA',0,'C'],['C',.7,'C'],['O',1.1,'O']]){
 const angle=i*100*Math.PI/180;
 atoms.push(`ATOM  ${String(++serial).padStart(5)} ${name.padStart(4)} ALA A${String(i).padStart(4)}    ${(2.3*Math.cos(angle)+dx).toFixed(3).padStart(8)}${(2.3*Math.sin(angle)).toFixed(3).padStart(8)}${(i*1.5).toFixed(3).padStart(8)}  1.00 90.00          ${element.padStart(2)}`);
}
async function open(page,data=payload,{imageFailure=false}={}){
 const record={id:rid,tool:'mcsa-query',title:'M-CSA enzyme records',status:'completed',evidence_type:'Database annotation',created:1794800000,inputs:{query_id:'1'},payload:data};
 await page.route('**/api/workspace/**',route=>route.fulfill({json:record}));
 await page.route('**/api/query/enzyme-full-info/*/structure',route=>route.fulfill({json:{success:true,structure_format:'pdb',structure_data:atoms.join('\n')+'\nEND\n',source:{version:6,kind:'predicted'}}}));
 await page.route('https://www.ebi.ac.uk/thornton-srv/m-csa/media/schemes_svg/**',route=>imageFailure?route.abort():route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300"><rect width="600" height="300" fill="white"/><text x="60" y="150" font-size="24">Test-only mechanism diagram</text></svg>'}));
 await page.goto(`/enzymind/results/${rid}`);
 await expect(page.locator('.mcsa-result')).toBeVisible();
}

test('mechanism explorer draws chemical structures, expands diagrams and keeps proposals separate',async({page})=>{
 await open(page);
 await expect(page.locator('.mcsa-identity')).toContainText('First paragraph.');
 await expect(page.locator('.mcsa-identity')).not.toContainText('<p>');
 await page.locator('.reaction-layout').scrollIntoViewIfNeeded();
 await expect(page.locator('.compound-card .chemical-preview img').first()).toBeVisible({timeout:60000});
 await page.locator('.mechanism-figure').scrollIntoViewIfNeeded();
 await expect(page.locator('.mechanism-figure img')).toBeVisible();
 await expect(page.locator('.mechanism-figure button.expand-preview')).toBeEnabled();
 await page.locator('.mechanism-figure button.expand-preview').click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await expect.poll(async()=>{const b=await page.getByRole('dialog').boundingBox();return Math.abs(b.y+b.height/2-500)<3 && b.y>=0;}).toBe(true);
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Next →',exact:true}).click();
 await expect(page.locator('.step-heading')).toContainText('Products');
 await page.getByRole('button',{name:/Proposal 2/}).click();
 await expect(page.locator('.mechanism-summary')).toContainText('Historical proposal');
 await expect(page.locator('.literature')).toContainText('Second source reference');
 await expect(page.locator('.literature')).not.toContainText('First source reference');
 await expect(page.locator('.mechanism-step')).toHaveCount(0);
});

test('UniProt residues link to the model while PDB and author numbering stay separate',async({page})=>{
 await open(page);
 await page.getByLabel('Reference structure',{exact:true}).scrollIntoViewIfNeeded();
 await expect(page.locator('.viewer-caption')).toBeVisible();
 await page.getByRole('button',{name:'Locate Ala8',exact:true}).click();
 await expect(page.locator('.residue-selection')).toContainText('ALA 8');
 await expect(page.locator('.sequence-row button[aria-pressed=true]')).toHaveAttribute('title','A · residue 8');
 await page.getByRole('button',{name:'PDB',exact:true}).click();
 await expect(page.locator('.residue-table')).toContainText('Ala52');
 await expect(page.locator('.residue-table')).toContainText('35');
 await expect(page.locator('.residue-table button')).toHaveCount(0);
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download residues CSV'}).click();
 expect((await download).suggestedFilename()).toBe('mcsa-1-residues.csv');
});

test('missing diagrams and older partial records preserve readable evidence',async({page})=>{
 await open(page,{...payload,sequence_info:null,reaction:null,cofactors:null},{imageFailure:true});
 await page.locator('.mechanism-figure').scrollIntoViewIfNeeded();
 await expect(page.locator('.mechanism-figure')).toContainText('The source diagram could not load');
 await expect(page.locator('.mechanism-step')).toContainText('First source step');
 await expect(page.locator('.mcsa-result')).toContainText('No matching reference sequence');
 await expect(page.locator('.residue-table')).toContainText('Synthetic role annotation.');
 await expect(page.locator('.residue-table button')).toHaveCount(0);
});

test('narrow cards contain horizontal tables, retain folding and keep database HTML inert',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await open(page,{...payload,basic_info:{...payload.basic_info,description:'<script>window.mcsaInjected=1</script><img src=x onerror="window.mcsaInjected=1">Safe text.'}});
 await expect(page.locator('.mcsa-identity')).toContainText('Safe text.');
 expect(await page.evaluate(()=>window.mcsaInjected)).toBeUndefined();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.getByText('Numbered sequence',{exact:false}).first().click();
 await expect(page.locator('.sequence-preview')).not.toBeVisible();
});

test('not-found records do not render empty scientific assertions',async({page})=>{
 await open(page,{found:false,message:'No matching M-CSA record.'});
 await expect(page.locator('.mcsa-result')).toContainText('No matching M-CSA record.');
 await expect(page.locator('.mcsa-identity')).toHaveCount(0);
});
