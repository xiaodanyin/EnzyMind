import {test,expect} from './fixtures.mjs';

// Synthetic data exercises interactions; not a biological prediction.
const sequence='A'.repeat(25);
let serial=0;
const atoms=[];
for(let i=1;i<=25;i++)for(const [name,dx,element] of [['N',-.7,'N'],['CA',0,'C'],['C',.7,'C'],['O',1.1,'O']]){
  const angle=i*100*Math.PI/180;
  atoms.push(`ATOM  ${String(++serial).padStart(5)} ${name.padStart(4)} ALA A${String(i).padStart(4)}    ${(2.3*Math.cos(angle)+dx).toFixed(3).padStart(8)}${(2.3*Math.sin(angle)).toFixed(3).padStart(8)}${(i*1.5).toFixed(3).padStart(8)}  1.00 90.00          ${element.padStart(2)}`);
}
const model={success:true,uniprot_id:'P00176',structure_data:atoms.join('\n')+'\nEND\n',structure_format:'pdb',source:{kind:'predicted',version:6,sequence_start:1,sequence_end:25,mean_plddt:90}};
const payload={success:true,uniprot_id:'P00176',protein_name:'Synthetic enzyme fixture',organism:{scientificName:'Test species'},gene_names:['TEST1'],reviewed:true,
  sequence_info:{sequence,length:25,mol_weight:2500},function:'Function text for interface validation.',
  functional_sites:[{type:'Active site',start:8,end:8,description:'Synthetic catalytic annotation'},{type:'Binding site',start:14,end:14,ligand:'Test ligand'}],
  catalytic_activities:[{ec_number:'1.1.1.1',reaction:'Synthetic substrate + cofactor = product',rhea_id:'17149'}],
  kinetic_parameters:{km:[{value:2,unit:'mM',substrate:'Example A'},{value:20,unit:'uM',substrate:'Example B'}],vmax:[]},
  structure_references:[{id:'1ABC',method:'X-ray',resolution:'2.0 A',chains:'A=1-25'}]};
async function submit(page,data=payload,structure=model){
  await page.route('**/api/query/enzyme-full-info',r=>r.fulfill({json:data}));
  await page.route('**/api/query/enzyme-full-info/*/structure',r=>r.fulfill(structure?{json:structure}:{status:502,json:{detail:'Reference download unavailable for this test.'}}));
  await page.goto('/enzymind/utility/enzyme-info');
  await page.locator('#protein-query').fill('P00176');
  await page.locator('.tool-form button[type="submit"]').click();
  await expect(page.locator('.enzyme-identity')).toBeVisible();
  await page.getByLabel('Reference structure', {exact:true}).scrollIntoViewIfNeeded();
}

test('reuse sequence and model viewers with validated two-way site selection and downloads',async({page})=>{
  await submit(page);
  await page.locator('.protein-workbench').scrollIntoViewIfNeeded();
  await expect(page.locator('.viewer-caption')).toBeVisible();
  await expect(page.locator('.mapping-status')).toContainText('2 of 2 annotations mapped');
  await page.getByRole('button',{name:'Locate A8',exact:true}).click();
  await expect(page.locator('.residue-selection')).toContainText('ALA 8');
  await expect(page.locator('.sequence-row button[aria-pressed="true"]')).toHaveAttribute('title','A · residue 8');
  await page.locator('.sequence-row button[title="A · residue 14"]').click();
  await expect(page.locator('.residue-selection')).toContainText('ALA 14');
  await expect(page.locator('.enzyme-info-result .protein-legend')).toContainText('Active site');
  const fasta=page.waitForEvent('download');await page.getByRole('button',{name:'Download FASTA'}).click();
  expect((await fasta).suggestedFilename()).toBe('P00176.fasta');
  await expect(page.locator('.enzyme-info-result .scientific-chart')).toHaveCount(2);
  await expect(page.locator('.enzyme-info-result .scientific-chart').first()).toContainText('Km · mM');
  await expect(page.locator('.enzyme-info-result .scientific-chart').nth(1)).toContainText('Km · uM');
});

test('structure outage and missing fields preserve partial results without fabricated zeros',async({page})=>{
  await submit(page,{success:true,uniprot_id:'P00176',partial:true,sequence_info:{sequence:'ACDE'},functional_sites:[],catalytic_activities:[]},null);
  await expect(page.locator('.structure-empty')).toContainText('Structure unavailable');
  await expect(page.locator('.sequence-preview')).toBeVisible();
  await expect(page.getByLabel('Reported kinetic parameters')).toContainText('unavailable in this snapshot');
  await expect(page.locator('.identity-stats')).not.toContainText('Site annotations');
  await page.getByRole('button',{name:'Retry structure'}).click();
  await expect(page.locator('.structure-empty')).toContainText('Structure unavailable');
});

test('sequence mismatch suppresses overlays and location claims',async({page})=>{
  await submit(page,{...payload,sequence_info:{sequence:'C'.repeat(25),length:25}});
  await expect(page.locator('.inline-notice')).toContainText('Site overlays and sequence linking are disabled');
  await page.getByRole('button',{name:'Locate C8',exact:true}).click();
  await expect(page.locator('.residue-selection')).toHaveCount(0);
  await expect(page.locator('.enzyme-info-result')).toContainText('No validated matching coordinate');
});

test('narrow result panel keeps tables and sequence scrolling inside the card',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await submit(page,payload,null);
  await expect(page.locator('.structure-empty')).toContainText('Structure unavailable');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
  const table=page.locator('.annotation-table');await table.scrollIntoViewIfNeeded();
  await expect(table).toContainText('Synthetic catalytic annotation');
  await page.locator('.enzyme-info-result details').filter({has:page.locator('summary', {hasText:'Numbered amino acid sequence'})}).locator('summary').click();
  await expect(page.locator('.sequence-preview')).not.toBeVisible();
});
