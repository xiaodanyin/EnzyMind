import {test,expect} from './fixtures.mjs';
const rid='12345678-1234-4234-8234-123456789abc';
const sequence='ACDEFGHIKLMNPQRSTVWY'.repeat(22);
function record(overrides={}){return {id:rid,tool:'kcat',title:'Saved scientific result',status:'completed',evidence_type:'Prediction',created:1794200000,expires_at:1801976000,inputs:{enzyme_query:sequence,smiles:'[13CH3:1][C@H](O)C'},payload:{kcat:2.3},...overrides};}
async function mock(page,result){await page.route('**/enzymind/api/workspace/**',route=>{const path=new URL(route.request().url()).pathname;return route.fulfill({json:path.endsWith('/sessions')?{sessions:[]}:path.endsWith('/usage')?{limit:10,remaining:10}:path.endsWith('/results')?{results:result?[result]:[]}:result||{}});});}
async function drag(page,locator,dx){const box=await locator.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+dx,box.y+box.height/2,{steps:8});await page.mouse.up();}

test('Agent resizes all three columns, persists widths, clamps bounds and keeps mobile drawers',async({page})=>{
 await mock(page);await page.goto('/enzymind/agent');
 await page.getByRole('button',{name:/^Results/}).click();
 const left=page.getByRole('separator',{name:'Resize conversations panel'}),right=page.getByRole('separator',{name:'Resize results panel'});
 await expect(left).toBeVisible();await expect(right).toBeVisible();
 const initialLeft=Number(await left.getAttribute('aria-valuenow')),initialRight=Number(await right.getAttribute('aria-valuenow'));
 await drag(page,left,60);await expect(left).toHaveAttribute('aria-valuenow',String(initialLeft+60));
 await drag(page,right,80);await expect(right).toHaveAttribute('aria-valuenow',String(initialRight-80));
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('enzymind_agent_layout_v1')));
 expect(await page.locator('.conversation-pane').evaluate(el=>el.clientWidth)).toBeGreaterThanOrEqual(360);
 await page.screenshot({path:'/tmp/enzymind-agent-resized.png'});
 await page.reload();await page.getByRole('button',{name:/^Results/}).click();
 await expect(left).toHaveAttribute('aria-valuenow',String(Math.round(saved.left)));
 await expect(right).toHaveAttribute('aria-valuenow',String(Math.round(saved.right)));
 await right.focus();await page.keyboard.press('ArrowLeft');await expect(right).toHaveAttribute('aria-valuenow',String(Math.round(saved.right)+16));
 await page.keyboard.press('End');expect(await page.locator('.conversation-pane').evaluate(el=>el.clientWidth)).toBeGreaterThanOrEqual(360);
 await page.getByRole('button',{name:'Close result inspector'}).click();await expect(right).toHaveCount(0);
 await left.dblclick();await expect(left).toHaveAttribute('aria-valuenow','250');
 await page.setViewportSize({width:390,height:844});await expect(left).not.toBeVisible();
 await page.getByRole('button',{name:'Open conversations'}).click();await expect(page.locator('.workspace-sidebar')).toBeVisible();
 await page.getByRole('button',{name:'Close conversation menu',exact:true}).last().click();
 await page.getByRole('button',{name:/^Results/}).click();await expect(page.locator('.result-inspector')).toBeVisible();await expect(right).not.toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('result detail shows paginated sequence, a real Ketcher depiction and exact source inputs',async({page})=>{
 const result=record();await mock(page,result);await page.goto(`/enzymind/results/${rid}`);
 const inputs=page.getByRole('region',{name:'Enzyme and molecule pairing'});
 await expect(inputs).toContainText('440 residues');await expect(inputs.locator('.sequence-row')).toHaveCount(10);
 await inputs.getByRole('button',{name:'Next'}).click();await expect(inputs.locator('.sequence-row').first()).toContainText('301');
 const image=inputs.locator('.chemical-preview img');await inputs.locator('.chemical-preview').scrollIntoViewIfNeeded();
 await expect(image).toBeVisible({timeout:60000});expect(await image.evaluate(el=>el.complete&&el.naturalWidth>0)).toBe(true);
 await expect(inputs).toContainText(result.inputs.smiles);
 await page.screenshot({path:'/tmp/enzymind-result-inputs.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('reaction inputs render both sides and invalid saved SMILES retain the literal source',async({page})=>{
 let result=record({tool:'enzyme-type',inputs:{query:'CCO>>CC=O',k:5},payload:{recommendations:[]}});await mock(page,result);await page.goto(`/enzymind/results/${rid}`);
 await expect(page.locator('.chemical-preview img')).toBeVisible({timeout:60000});await expect(page.locator('.result-inputs')).toContainText('Reactants → products');
 await page.unroute('**/enzymind/api/workspace/**');result=record({inputs:{smiles:'INVALID SMILES ('}});await mock(page,result);await page.reload();
 await expect(page.locator('.chemical-preview')).toContainText('could not be drawn',{timeout:60000});await expect(page.locator('.result-inputs pre')).toHaveText('INVALID SMILES (');
});

test.describe('English deletion dates',()=>{
 test.use({locale:'zh-CN',timezoneId:'Asia/Shanghai'});
 test('remain English with a Chinese browser locale',async({page})=>{
  const result=record({expires_at:Date.UTC(2027,1,7,12)/1000});await mock(page,result);await page.goto('/enzymind/results');
  await expect(page.locator('.expiry-badge time')).toHaveText('Feb 7, 2027');await expect(page.locator('.expiry-badge time')).toHaveAttribute('datetime','2027-02-07T12:00:00.000Z');
 });
});

test('EC results name every hierarchy level, including multiple candidates and unknown labels',async({page})=>{
 const result=record({tool:'ec',inputs:{query:'P00761'},payload:{ec_number:'3.4.21.4;1.1.1.1;3.4.21.9999'}});await mock(page,result);await page.goto(`/enzymind/results/${rid}`);
 const ec=page.getByRole('region',{name:'EC classification names'});
 await expect(ec).toContainText('Hydrolases');await expect(ec).toContainText('Acting on peptide bonds (peptidases)');await expect(ec).toContainText('Serine endopeptidases');await expect(ec).toContainText('trypsin');
 await expect(ec.locator('details')).toHaveCount(3);await ec.locator('summary').nth(1).click();await expect(ec.locator('details').nth(1)).toContainText('alcohol dehydrogenase');
 await ec.locator('summary').nth(2).click();await expect(ec.locator('details').nth(2)).toContainText('Name unavailable in this reference');
 await expect(page.locator('.result-inputs')).toContainText('Only the accession was saved');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'/tmp/enzymind-ec-mobile.png',fullPage:true});
});

test('recommendation results include EC names and preserve original scores',async({page})=>{
 const result=record({tool:'enzyme-type',inputs:{query:'CCO>>CC=O'},payload:{recommendations:[{ec_number:'1.1.1.1',confidence:27.5},{ec_number:'3.4.-.-',confidence:12.3}]}});await mock(page,result);await page.goto(`/enzymind/results/${rid}`);
 await expect(page.locator('.ec-classifications')).toContainText('Oxidoreductases');await expect(page.locator('.ec-classifications')).toContainText('With NAD(+) or NADP(+) as acceptor');
 await expect(page.locator('.research-result')).toContainText('27.5');await expect(page.locator('.research-result')).toContainText('12.3');
 await page.locator('.ec-classifications summary').nth(1).click();await expect(page.locator('.ec-classifications details').nth(1)).toContainText('Not specified by this EC number');
});

test('narrowing an active conversation keeps toolbar, draft and memory usable',async({page})=>{
 const sid='cccccccc-cccc-4ccc-8ccc-cccccccccccc',now=Date.now()/1000;
 const session={id:sid,title:'Width regression',created:now,updated:now,summary:'Saved research context',summarized_count:2,memory_revision:1};
 await page.route('**/enzymind/api/workspace/**',route=>{
  const path=new URL(route.request().url()).pathname;
  return route.fulfill({json:path.endsWith('/sessions')?{sessions:[session]}:path.endsWith('/results')?{results:[]}:path.endsWith('/usage')?{limit:10,remaining:9}:{...session,turns:[{id:rid,created:now,status:'completed',message:'Classify P00761',output:'Saved response',events:[],references:[]}],results:[]}});
 });
 await page.goto('/enzymind/agent');await page.getByRole('button',{name:/Width regression/}).click();
 await page.locator('textarea').fill('Keep this unsent question');await page.getByRole('button',{name:/^Results/}).click();
 const divider=page.getByRole('separator',{name:'Resize results panel'});await divider.focus();await page.keyboard.press('End');
 const pane=await page.locator('.conversation-pane').boundingBox();
 for(const button of await page.locator('.workspace-topbar button').all())if(await button.isVisible()){const box=await button.boundingBox();expect(box.x).toBeGreaterThanOrEqual(pane.x);expect(box.x+box.width).toBeLessThanOrEqual(pane.x+pane.width+1);}
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();await expect(page.locator('.memory-panel')).toBeVisible();await expect(page.locator('textarea')).toHaveValue('Keep this unsent question');
 await page.getByRole('button',{name:'Close conversation memory'}).click();
 const box=await divider.boundingBox();await page.mouse.move(box.x+4,box.y+80);await page.mouse.down();await page.mouse.move(box.x+24,box.y+80);
 await divider.dispatchEvent('pointercancel');await expect(page.locator('.agent-workspace')).not.toHaveClass(/is-resizing/);await page.mouse.up();
 expect(await page.evaluate(()=>document.body.style.cursor)).toBe('');
 await page.screenshot({path:'/tmp/enzymind-agent-narrow-chat.png'});
});
