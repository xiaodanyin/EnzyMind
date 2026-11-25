import {test,expect} from './fixtures.mjs';
import {TOOLS} from '../../src/config/tools.js';

const id='11111111-1111-4111-8111-111111111111';
const fixtures={recognize:{is_enzyme:true,confidence:.92},ec:{ec_number:'3.4.21.4'},substrate:{is_substrate:true,confidence:.81},kcat:{kcat:.00002,unit:'s^-1'},km:{km:2.5,unit:'mM'},'enzyme-type':{recommendations:[{ec_number:'3.1.1.1',confidence:.8},{ec_number:'3.1.1.2',confidence:.1}]},'active-sites':{results:[{sequence:'ACDEFGHIK',active_data:[[2,'CYS','','Catalytic Site',.9]],residue_labels:[0,2]}]},structure:{structure_data:'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 92.00           C\nATOM      2  CA  GLY A   2       1.500   2.000   0.000  1.00 65.00           C\nEND\n'},parameters:{sequence_length:9,parameters:{molecular_weight:1100},amino_acid_composition:[{residue:'A',name:'Ala',count:1,percent:11.111}]},blast:{query_length:100,num_results:1,alignments:[{title:'Test alignment fixture',query:'ACDEFG',match:'ACD FG',subject:'ACDVFG',query_start:1,query_end:60,alignment_length:60,identities:54,e_value:1e-12,length:140}]},'enzyme-info':{uniprot_id:'P00761',protein_name:'Trypsin',function:'Test-only database response'}};
function record(tool,inputs={}){return {id,tool:tool.id,title:tool.title,status:'completed',evidence_type:tool.analysis?'Calculated properties':'Prediction',created:1700000000,duration:1,inputs,payload:{success:true,...fixtures[tool.id]}};}
for(const tool of TOOLS){
 test(`${tool.title}: diagram, valid input, result and export`,async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let submitted;
  await page.route('**/enzymind/api/**',async route=>{
   if(route.request().method()==='POST'&&route.request().url().endsWith(tool.endpoint)){
    submitted=route.request().postDataJSON();const r=record(tool,submitted);const {payload,...meta}=r;return route.fulfill({json:{...payload,workspace_result:meta}});
   }
   return route.fulfill({json:{results:[],sessions:[]}});
  });
  await page.goto(`/enzymind${tool.path}`);
  const diagram=page.locator('.model-workflow svg').first();
  // The shared component's semantic figure is above the working inputs.
  await expect(page.getByText('FROM INPUT TO PREDICTION',{exact:true}).or(page.getByText('ANALYSIS WORKFLOW',{exact:true}))).toBeVisible();
  const form=page.locator('.tool-form');
  const retention=page.locator('.retention-notice').first();
  await expect(retention).toContainText('automatically deleted after 90 days');
  expect((await retention.boundingBox()).y).toBeLessThan((await form.boundingBox()).y);
  expect((await page.locator('svg[role="group"]').first().boundingBox()).y).toBeLessThan((await form.boundingBox()).y);
  if(tool.protein!==false)await page.getByRole('button',{name:'Load protein example'}).click();
  if(tool.molecule && tool.molecule!=='optional-reaction')await page.getByRole('button',{name:/Load (substrate|reaction) example/}).click();
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('.workbench-result')).toBeVisible();
  expect(submitted).toBeTruthy();
  if(tool.id==='enzyme-type')expect(submitted.k).toBe(5);
  if(tool.id==='kcat')await expect(page.locator('.result-metrics')).toContainText('2.00000e-5');
  if(tool.id==='blast'){await expect(page.locator('.blast-overview')).toContainText('60.0%');await expect(page.locator('.blast-overview')).toContainText('90.0%');}
  if(['recognize','substrate','parameters','enzyme-type'].includes(tool.id))await expect(page.locator('.chart-canvas svg').first()).toBeVisible();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export JSON',exact:true}).click();expect((await download).suggestedFilename()).toMatch(/\.json$/);
  await page.screenshot({path:`/tmp/enzymind-browser-artifacts/${tool.id}.png`,fullPage:true});
  expect(errors).toEqual([]);
 });
}
test('FASTA selection, validation, mobile layout and Home shortcuts',async({page})=>{
 await page.goto('/enzymind/predict/enzyme');
 await page.locator('#protein-query').fill('>first\nACDE\n>second\nFGHI');
 await page.locator('.tool-form button[type="submit"]').click();
 await expect(page.locator('.run-error')).toContainText('Choose one');
 await page.locator('.protein-input select').selectOption('1');
 await expect(page.locator('.protein-input')).toContainText('4');
 await page.locator('#protein-query').fill('ACDE1*');
 await page.locator('.tool-form button[type="submit"]').click();
 await expect(page.locator('.run-error')).toContainText('Unsupported');
 await page.setViewportSize({width:390,height:844});
 await page.goto('/enzymind/predict/km');
 await expect(page.locator('svg[role="group"]').first()).toHaveAttribute('viewBox','0 0 360 432');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.goto('/enzymind/');
 await expect(page.locator('.hero')).toBeVisible();
 await page.getByRole('searchbox',{name:'Find a tool'}).fill('kinetic');
 await expect(page.locator('.directory-tool').first()).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/home-mobile.png',fullPage:true});
});
test('in-flight model requests survive navigation without resubmitting',async({page})=>{
 let release;const waiting=new Promise(r=>release=r);let calls=0;
 await page.route('**/api/recognize/enzyme',async route=>{calls++;await waiting;const r=record(TOOLS[0]);const {payload,...meta}=r;await route.fulfill({json:{...payload,workspace_result:meta}});});
 await page.goto('/enzymind/predict/enzyme');await page.getByRole('button',{name:'Load protein example'}).click();await page.locator('.tool-form button[type="submit"]').click();await expect(page.locator('.run-status')).toBeVisible();
 await page.getByRole('link',{name:'Home',exact:true}).click();release();await page.locator('.directory-tool').filter({hasText:'Enzyme Recognition'}).click();
 await expect(page.locator('.workbench-result')).toBeVisible();expect(calls).toBe(1);await expect(page.locator('#protein-query')).toHaveValue('P00761');
});
test('Ketcher synchronizes molecule text, canvas, stereochemistry and clear',async({page})=>{
 await page.goto('/enzymind/predict/kcat');await page.getByRole('button',{name:'Draw with Ketcher'}).click();
 await expect(page.locator('.ketcher-sync')).toHaveText('SMILES linked',{timeout:60000});
 const frame=page.frames().find(f=>f.url().includes('/ketcher/index.html'));expect(frame).toBeTruthy();
 await page.locator('#chemical-smiles').fill('[13CH3:1][C@H](O)C');
 await expect.poll(()=>frame.evaluate(()=>window.ketcher.getSmiles(false))).toContain('13CH3');
 const serialized=await frame.evaluate(()=>window.ketcher.getSmiles(false));expect(serialized).toContain('@');
 await expect(page.locator('#chemical-smiles')).toHaveValue('[13CH3:1][C@H](O)C');
 await frame.evaluate(()=>window.ketcher.setMolecule('[13CH3:1][C@H:2](O)[NH3+]'));
 await expect(page.locator('#chemical-smiles')).toHaveValue(/:2\]/);
 const mapped=await page.locator('#chemical-smiles').inputValue();expect(mapped).toContain(':2]');expect(mapped).toContain('[NH3+]');expect(mapped).toContain('@');
 const before=await frame.evaluate(()=>window.ketcher.getInchi());await frame.evaluate(s=>window.ketcher.setMolecule(s),mapped);expect(await frame.evaluate(()=>window.ketcher.getInchi())).toBe(before);
 await frame.evaluate(()=>window.ketcher.setMolecule('CC(=O)O'));
 await expect(page.locator('#chemical-smiles')).toHaveValue(/^(CC\(=O\)O|CC\(O\)=O)$/);
 await frame.evaluate(()=>window.ketcher.editor.clear());
 await expect(page.locator('#chemical-smiles')).toHaveValue('');
 await page.locator('#chemical-smiles').fill('C1CC');
 await expect(page.locator('.ketcher-message')).toContainText('could not be updated');
 await expect(page.locator('#chemical-smiles')).toHaveValue('C1CC');
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/ketcher.png',fullPage:true});
});
test('Ketcher reaction mode flushes the latest drawing into the request',async({page})=>{
 let submitted;await page.route('**/api/query/enzyme-type/top-k',route=>{submitted=route.request().postDataJSON();return route.fulfill({json:{success:true,...fixtures['enzyme-type']}});});
 await page.goto('/enzymind/predict/recommendation');await page.getByRole('button',{name:'Draw with Ketcher'}).click();
 await expect(page.locator('.ketcher-sync')).toHaveText('SMILES linked',{timeout:60000});
 const frame=page.frames().find(f=>f.url().includes('/ketcher/index.html'));
 await frame.evaluate(()=>window.ketcher.setMolecule('[CH3:1][OH:2]>>[CH2:1]=[O:2]'));
 await page.locator('.tool-form button[type="submit"]').click();await expect(page.locator('.workbench-result')).toBeVisible();expect(submitted.query).toContain('>>');expect(submitted.query).toContain(':1]');
});
test('Mol* renders, links residues, switches styles and exports a real snapshot',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.ENZYMIND_VIEWER_TEST_URL || 'http://127.0.0.1:3011/enzymind/tests/viewer.html');
 await expect(page.locator('.viewer-caption')).toBeVisible({timeout:60000});
 await expect(page.locator('.molecule-canvas canvas')).toBeVisible();
 await page.getByRole('button',{name:'ALA 8',exact:true}).click();await expect(page.locator('.mapping-note').first()).toContainText('No unique');
 await page.getByRole('combobox',{name:'Chain',exact:true}).selectOption('A');await page.getByRole('button',{name:'ALA 8',exact:true}).click();await expect(page.locator('.residue-selection')).toContainText('chain A');
 await expect(page.locator('.sequence-track button.selected')).toHaveCount(1);
 await expect(page.locator('.label-overlay text').first()).toContainText('ALA');
 // Allow the 300 ms focus animation to finish before checking camera tracking.
 await page.waitForTimeout(350);
 const anchor=page.locator('.label-overlay line').first();
 const before=await anchor.getAttribute('x1');
 const canvas=await page.locator('.molecule-canvas canvas').boundingBox();
 await page.mouse.move(canvas.x+canvas.width*.45,canvas.y+canvas.height*.5);await page.mouse.down();await page.mouse.move(canvas.x+canvas.width*.62,canvas.y+canvas.height*.55,{steps:12});await page.mouse.up();
 await expect.poll(()=>anchor.getAttribute('x1')).not.toBe(before);
 for(const style of ['stick','surface','cartoon']){await page.getByRole('combobox',{name:'View',exact:true}).selectOption(style);await expect(page.locator('.viewer-caption')).toBeVisible();}
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Save PNG'}).click();expect((await download).suggestedFilename()).toMatch(/\.png$/);
 await page.getByRole('combobox',{name:'Color',exact:true}).selectOption('confidence');await expect(page.locator('.protein-legend')).toContainText('pLDDT');
 await expect(page.locator('.chart-canvas svg')).toBeVisible();await page.screenshot({path:'/tmp/enzymind-browser-artifacts/molstar.png',fullPage:true,animations:'disabled'});expect(errors).toEqual([]);
});
test('failed model responses keep inputs and the saved failure record',async({page})=>{
 let calls=0;await page.route('**/enzymind/api/recognize/enzyme',route=>{calls++;const r=record(TOOLS[0]);const {payload,...meta}=r;return route.fulfill({status:503,json:{success:false,error:'Test service unavailable',workspace_result:{...meta,status:'failed'}}});});
 await page.goto('/enzymind/predict/enzyme');await page.getByRole('button',{name:'Load protein example'}).click();await page.locator('.tool-form button[type="submit"]').click();
 await expect(page.locator('.run-error')).toContainText('Test service unavailable');await expect(page.locator('.research-result .result-state')).toHaveText('Failed');await expect(page.locator('#protein-query')).toHaveValue('P00761');expect(calls).toBe(1);
});
test('method diagrams have no download button and scientific chart exports still work',async({page})=>{
 await page.route('**/enzymind/api/recognize/enzyme',route=>{const r=record(TOOLS[0]);const {payload,...meta}=r;return route.fulfill({json:{...payload,workspace_result:meta}});});
 await page.goto('/enzymind/predict/enzyme');
 await expect(page.locator('.model-workflow svg').first()).toBeVisible();
 await expect(page.getByRole('button',{name:'Download method diagram as SVG'})).toHaveCount(0);
 await page.getByRole('button',{name:'Load protein example'}).click();await page.locator('.tool-form button[type="submit"]').click();await expect(page.locator('.chart-canvas svg')).toBeVisible();
 for(const type of ['SVG','PNG','CSV']){const event=page.waitForEvent('download');await page.locator('.chart-actions').getByRole('button',{name:type,exact:true}).click();expect((await event).suggestedFilename()).toMatch(new RegExp('\\.'+type.toLowerCase()+'$'));}
});
