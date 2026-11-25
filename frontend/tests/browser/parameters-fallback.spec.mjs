import {test,expect} from './fixtures.mjs';

for(const method of ['remote','local_fallback']){
 test(`Protein Parameters declares ${method} calculation source and retains export`,async({page})=>{
  const local=method==='local_fallback';
  const source={method,name:local?'Biopython ProteinAnalysis':'ExPASy ProtParam',...(local?{version:'1.86'}:{})};
  await page.route('**/api/query/protein-physchem',route=>route.fulfill({json:{result:'## ProtParam Results',data:{success:true,parameters:{molecular_weight:436.44,theoretical_pi:4.0,gravy:-2.675},source,amino_acid_composition:[{residue:'A',count:1,percent:25}]}}}));
  await page.goto('/enzymind/utility/parameters');
  await page.getByRole('button',{name:'Load protein example'}).click();
  await page.locator('.tool-form button[type="submit"]').click();
  await expect(page.locator('.result-state')).toHaveText('Completed');
  await expect(page.locator('.calculation-source')).toContainText(source.name);
  if(local)await expect(page.locator('.calculation-source')).toContainText('may differ slightly from ExPASy');
  else await expect(page.locator('.calculation-source')).not.toContainText('Local fallback');
  await page.getByText('Input & provenance',{exact:true}).click();
  await expect(page.locator('.result-details[open]')).toContainText(source.name);
  const event=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export JSON',exact:true}).click();
  expect((await event).suggestedFilename()).toMatch(/\.json$/);
 });
}
