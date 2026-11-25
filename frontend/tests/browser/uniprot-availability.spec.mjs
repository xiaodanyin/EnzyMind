import {test,expect} from './fixtures.mjs';

for (const mode of ['partial','stale','fresh']) {
  test(`Enzyme information preserves ${mode} annotation provenance`, async ({page}) => {
    const partial = mode === 'partial';
    const source = partial
      ? {name:'Local UniProt snapshot',method:'local_snapshot',partial:true,snapshot_created_at:'2026-06-14T18:34:36Z'}
      : {name:'UniProt API response cache',method:'uniprot_cache',stale:mode==='stale',retrieved_at:'2026-11-15T10:00:00Z',note:'Previously retrieved UniProt annotations.'};
    const payload = {success:true,is_enzyme:true,uniprot_id:'P00176',partial,source,
      warnings:partial?['Kinetic parameters are unavailable in this snapshot; this does not mean they have not been reported.']:[],
      unavailable_sections:partial?['kinetic_parameters']:[],
      sequence_info:{length:8,sequence:'ACDEFGHI'},
      catalytic_activities:[{ec_number:'1.14.14.1',reaction:'Example annotated reaction'}],
      kinetic_parameters:partial?null:{km:[],vmax:[],kcat_note:''},functional_sites:[]};
    await page.route('**/api/query/enzyme-full-info', route=>route.fulfill({json:payload}));
    await page.route('**/api/query/enzyme-full-info/*/structure', route=>route.fulfill({status:404,json:{detail:'No reference model for this test fixture.'}}));
    await page.goto('/enzymind/utility/enzyme-info');
    await page.locator('#protein-query').fill('P00176');
    await page.locator('.tool-form button[type="submit"]').click();
    await expect(page.locator('.run-error')).toHaveCount(0);
    await expect(page.locator('.result-state')).toHaveText(partial?'Partial result':mode==='stale'?'Cached result':'Completed');
    await expect(page.getByRole('status',{name:'Annotation availability'})).toBeVisible();
    if (partial) {
      await expect(page.locator('.annotation-notice')).toContainText('does not mean they have not been reported');
      await expect(page.locator('.annotation-notice')).toContainText('Local snapshot:');
    } else await expect(page.locator('.annotation-notice')).toContainText('Retrieved from UniProt:');
    await expect(page.locator('.workbench-result')).toContainText('Example annotated reaction');
    const download=page.waitForEvent('download');
    await page.getByRole('button',{name:'Export JSON',exact:true}).click();
    expect((await download).suggestedFilename()).toMatch(/\.json$/);
  });
}
