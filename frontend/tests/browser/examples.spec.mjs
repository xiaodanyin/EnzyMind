import {test,expect} from './fixtures.mjs';
import {AGENT_EXAMPLES} from '../../src/config/agentExamples.js';
const id='11111111-1111-4111-8111-111111111111';
test('research examples are reviewable, cover the advertised workflows and never submit on selection',async({page})=>{
 let posts=0;
 await page.route('**/enzymind/api/workspace/**',route=>{
  if(route.request().method()==='POST')posts++;
  return route.fulfill({json:{sessions:[],results:[]}});
 });
 await page.goto('/enzymind/agent');
 await expect(page.locator('.example-grid>button')).toHaveCount(8);
 const coverage=new Set(AGENT_EXAMPLES.flatMap(e=>e.tools));
 for(const tool of ['recognize','ec','enzyme-info','enzyme-type','substrate','kcat','km','active-sites','features','mcsa-query','mcsa-residues','mcsa-mechanism','structure','parameters','blast','read-result'])expect(coverage.has(tool)).toBe(true);
 for(const example of AGENT_EXAMPLES.filter(e=>!e.requiresResult)){
  await page.locator('.example-grid').getByRole('button',{name:new RegExp(example.title.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}).click();
  await expect(page.locator('.example-detail')).toContainText(example.input);
  await expect(page.locator('.example-title h4')).toBeInViewport();
  await page.getByRole('button',{name:'Load starting question',exact:true}).click();
  await expect(page.locator('textarea')).toHaveValue(example.prompt);
 }
 await page.getByText('Try a follow-up after the first answer',{exact:true}).click();
 await page.getByRole('button',{name:'Load follow-up',exact:true}).click();
 await expect(page.locator('textarea')).toHaveValue(AGENT_EXAMPLES.filter(e=>!e.requiresResult).at(-1).followUp);
 expect(posts).toBe(0);
 await page.setViewportSize({width:390,height:844});
 await page.locator('.example-grid').getByRole('button',{name:/From reaction to enzyme class/}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.locator('.example-detail').scrollIntoViewIfNeeded();
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/agent-examples-mobile.png',animations:'disabled'});
});
test('saved-evidence example requires a real attachment and preserves it when loading the question',async({page})=>{
 let posts=0;
 const record={id,tool:'kcat',title:'Saved catalytic turnover',status:'completed',evidence_type:'Prediction',created:1700000000,inputs:{enzyme_query:'P00330',smiles:'CCO'},duration:1};
 await page.route('**/enzymind/api/workspace/**',route=>{
  if(route.request().method()==='POST')posts++;
  return route.fulfill({json:route.request().url().endsWith('/results')?{results:[record]}:{sessions:[]}});
 });
 await page.goto('/enzymind/agent');
 await page.locator('.example-grid').getByRole('button',{name:/Continue from saved evidence/}).click();
 await expect(page.getByRole('button',{name:'Load starting question',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Choose a saved result'}).click();
 await page.getByRole('button',{name:'＋ Attach',exact:true}).click();
 await page.getByRole('button',{name:'Close result inspector'}).click();
 await expect(page.getByRole('button',{name:'Load starting question',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Load starting question',exact:true}).click();
 await expect(page.locator('textarea')).toHaveValue(AGENT_EXAMPLES.find(e=>e.id==='saved-evidence').prompt);
 await expect(page.locator('.composer-area')).toContainText('Saved catalytic turnover');
 expect(posts).toBe(0);
});
