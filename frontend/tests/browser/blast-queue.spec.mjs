import {test,expect} from './fixtures.mjs';
const id='11111111-1111-4111-8111-111111111111';
function fixture(status='queued') {return {id,tool:'blast',title:'Sequence similarity · BLAST',status,evidence_type:'Sequence alignment',created:Date.now()/1000,duration:0,inputs:{query:'P00698',max_results:3,database:'nr'},payload:{success:true,status,request_id:'F60URTGC014',database:'nr',sequence:'ACDEFGHIK',last_checked_at:Date.now()/1000}};}

test('BLAST queue is saved, survives reload, updates the same result and never resubmits',async({page})=>{
 let current=fixture(),submissions=0,checks=0;
 await page.route('**/enzymind/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/query/blast')) {submissions++;const body=route.request().postDataJSON();expect(body.database).toBe('swissprot');expect(body.wait_for_result).toBe(false);current.inputs=body;current.payload.database='swissprot';const {payload,...meta}=current;return route.fulfill({json:{...payload,workspace_result:meta}});}
  if(path.endsWith(`/results/${id}/refresh`)) {checks++;current={...current,status:'completed',payload:{...current.payload,status:'completed',query_length:9,num_results:1,alignments:[{title:'Reviewed match',length:9,e_value:1e-10,query:'ACDEFGHIK',subject:'ACDEFGHIK',match:'ACDEFGHIK',alignment_length:9,identities:9,query_start:1,query_end:9}]}};return route.fulfill({json:current});}
  if(path.endsWith(`/results/${id}`))return route.fulfill({json:current});
  return route.fulfill({json:{results:[current],sessions:[]}});
 });
 await page.goto('/enzymind/utility/alignment');
 await page.getByRole('button',{name:'Load protein example'}).click();
 await page.getByText('Search options',{exact:true}).click();
 await page.getByLabel('Protein database').selectOption('swissprot');
 await page.getByRole('button',{name:'Search with BLAST'}).click();
 await expect(page.getByRole('region',{name:'BLAST search status'}).or(page.locator('.blast-pending'))).toContainText('F60URTGC014');
 await expect(page.locator('.result-state')).toHaveText('Queued at NCBI');
 await expect(page.locator('.result-metrics')).toHaveCount(0);
 await expect(page.locator('.blast-overview')).toHaveCount(0);
 await expect(page.locator('.blast-pending a')).toHaveAttribute('href','https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=Get&RID=F60URTGC014');
 await page.getByRole('link',{name:'Open result →'}).click();
 await expect(page).toHaveURL(new RegExp(`/results/${id}$`));
 await page.reload();
 await expect(page.locator('.blast-pending')).toContainText('Swiss-Prot');
 await page.setViewportSize({width:390,height:844});
 await expect(page.locator('.blast-pending')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
 await page.getByRole('button',{name:'Check status',exact:true}).click();
 await expect(page.locator('.result-state')).toHaveText('Completed');
 await expect(page.locator('.alignment-results')).toContainText('Reviewed match');
 await expect(page.locator('.blast-pending')).toHaveCount(0);
 expect(submissions).toBe(1);expect(checks).toBe(1);
});

test('saved BLAST background progress is visible without manual refresh',async({page})=>{
 let reads=0;const pending=fixture();
 await page.route('**/enzymind/api/workspace/results/**',route=>{
  reads++;return route.fulfill({json:reads===1?pending:{...pending,status:'completed',payload:{...pending.payload,status:'completed',num_results:0,alignments:[],query_length:9}}});
 });
 await page.goto(`/enzymind/results/${id}`);
 await expect(page.locator('.result-state')).toHaveText('Queued at NCBI');
 await expect(page.locator('.result-state')).toHaveText('Completed',{timeout:15000});
 expect(reads).toBeGreaterThan(1);
});

test('Results filters queued searches and paused jobs resume without a new search',async({page})=>{
 const record=fixture('paused');let resumed=0;
 await page.route('**/enzymind/api/**',route=>{
  const url=route.request().url();
  if(url.endsWith('/refresh')) {resumed++;record.status='queued';record.payload.status='queued';}
  return route.fulfill({json:url.endsWith('/results')?{results:[record]}:record});
 });
 await page.goto('/enzymind/results');
 await page.getByRole('combobox',{name:'Status',exact:true}).selectOption('paused');
 await expect(page.locator('.result-library-item')).toContainText('Checks paused');
 await page.locator('.result-library-item').click();
 await expect(page.locator('.blast-pending')).toContainText('24 hours');
 await page.getByRole('button',{name:'Check status',exact:true}).click();
 await expect(page.locator('.result-state')).toHaveText('Queued at NCBI');
 expect(resumed).toBe(1);
});

test('saved alignments compare segments and preserve gap coordinates on narrow screens', async ({page}) => {
  const current = fixture('completed');
  current.payload = {success:true, status:'completed', query_length:5, num_results:2, alignments:[
    {title:'First protein', length:5, query:'ACDFG', subject:'ACDFG', query_start:1, query_end:5,
      subject_start:1, subject_end:5, e_value:0},
    {title:'Second protein', length:20, query:'C-DF', subject:'CN-E', match:'C  +', query_start:2, query_end:4,
      subject_start:12, subject_end:14, e_value:3e-9},
  ]};
  await page.route('**/enzymind/api/workspace/results/**', route => route.fulfill({json:current}));
  await page.setViewportSize({width:390,height:844});
  await page.goto(`/enzymind/results/${id}`);
  const viewer = page.locator('.alignment-results');
  const matches = viewer.getByRole('button', {name:/Second protein/});
  await expect(viewer.locator('.hit-row').first()).toContainText('Full-length exact match');
  await matches.focus();
  await page.keyboard.press('Enter');
  await expect(matches).toHaveAttribute('aria-pressed','true');
  await expect(matches).toContainText('60.0%');
  await expect(matches).toContainText('25.0%');
  const detail = viewer.locator('.hit-detail');
  await expect(detail.getByRole('heading',{name:'Second protein'})).toBeVisible();
  await expect(detail.locator('.symbols .gap')).toHaveText('––');
  await expect(detail.locator('.symbols .positive')).toHaveText('+');
  await expect(detail.locator('.sequence-line').first().locator('.end')).toHaveText('4');
  await expect(detail.locator('.sequence-line').last().locator('.end')).toHaveText('14');
  await detail.getByRole('button',{name:'Differences (3)'}).click();
  const rows = detail.locator('.change-table tbody tr');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('Gap in query');
  await expect(rows.nth(1)).toContainText('Gap in hit');
  await expect(rows.nth(2)).toContainText('Positive substitution');
  await expect(rows.nth(2).locator('td').nth(1)).toHaveText('F 4');
  await expect(rows.nth(2).locator('td').nth(2)).toHaveText('E 14');
  await detail.getByRole('button',{name:/Expand .*residue differences/}).click();
  await expect(page.getByRole('dialog').locator('tbody tr')).toHaveCount(3);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(viewer.getByRole('button',{name:/First protein/})).toHaveAttribute('aria-pressed','false');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
