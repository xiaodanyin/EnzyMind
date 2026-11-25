import {test,expect} from './fixtures.mjs';
const sid='67777777-7777-4777-8777-777777777777',tid='68888888-8888-4888-8888-888888888888';
const token='sk-browser-test-only-never-real-key';
async function backend(page,{remaining=0,deny=false}={}){
 const requests=[],turns=[];const session={id:sid,title:'Billing test',created:Date.now()/1000,updated:Date.now()/1000,summary:'',summarized_count:0,memory_revision:0};
 const quota=()=>({used:10-remaining,limit:10,remaining,resets_at:'2026-11-10T00:00:00+08:00',date:'2026-11-09',timezone:'Asia/Shanghai'});
 await page.route('**/enzymind/api/workspace/**',async route=>{
  const r=route.request(),path=new URL(r.url()).pathname;requests.push({path,method:r.method(),headers:r.headers(),body:r.postData()});
  if(path.endsWith('/usage'))return route.fulfill({json:quota()});
  if(path.endsWith('/sessions'))return route.fulfill({json:r.method()==='POST'?session:{sessions:[session]}});
  if(path.endsWith('/results'))return route.fulfill({json:{results:[]}});
  if(r.method()==='POST'&&path.endsWith('/turns')){
   if(deny&&!r.headers()['x-deepseek-api-key']){remaining=0;return route.fulfill({status:402,json:{detail:{code:'daily_limit',message:'Today’s free conversations are used.',quota:quota()}}});}
   const body=r.postDataJSON();const turn={id:tid,session_id:sid,message:body.message,status:'completed',output:'Saved answer',references:[],events:[],created:Date.now()/1000,billing_mode:r.headers()['x-deepseek-api-key']?'byok':'free'};turns.push(turn);return route.fulfill({json:turn});
  }
  return route.fulfill({json:{...session,turns,results:[]}});
 });
 return requests;
}
test('quota exhausted opens an accessible key dialog and keeps the unsent question',async({page})=>{
 const calls=await backend(page);await page.goto('/enzymind/agent');
 await expect(page.locator('.agent-billing')).toContainText('0 / 10');await page.locator('#research-message').fill('Review this enzyme');
 await page.getByRole('button',{name:'Add DeepSeek key'}).click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.locator('#deepseek-api-key')).toBeFocused();
 await expect(page.locator('#deepseek-api-key')).toHaveAttribute('type','password');expect(calls.filter(r=>r.path.endsWith('/turns'))).toHaveLength(0);
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('#research-message')).toHaveValue('Review this enzyme');
 await page.getByRole('button',{name:'Add DeepSeek key'}).click();await page.locator('#deepseek-api-key').fill(token);await page.getByRole('button',{name:'Use this key',exact:true}).click();
 await expect(page.locator('.agent-billing')).toContainText('Using your DeepSeek key');expect(calls.filter(r=>r.path.endsWith('/turns'))).toHaveLength(0);
 expect(await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}))).not.toContain(token);
 await page.getByRole('button',{name:'Send question'}).click();await expect(page.locator('.agent-markdown')).toContainText('Saved answer');
 const submitted=calls.filter(r=>r.path.endsWith('/turns'));expect(submitted).toHaveLength(1);expect(submitted[0].headers['x-deepseek-api-key']).toBe(token);expect(submitted[0].body).not.toContain(token);
 expect(calls.filter(r=>!r.path.endsWith('/turns')).some(r=>r.headers['x-deepseek-api-key'])).toBe(false);
 await page.reload();await expect(page.locator('.agent-billing')).toContainText('0 / 10');await expect(page.getByRole('button',{name:'Forget key'})).toHaveCount(0);
});
test('server quota rejection preserves input and never silently switches billing',async({page})=>{
 const calls=await backend(page,{remaining:1,deny:true});await page.goto('/enzymind/agent');await page.locator('#research-message').fill('My pending question');await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.getByRole('dialog')).toBeVisible();await expect(page.locator('#research-message')).toHaveValue('My pending question');
 const submitted=calls.filter(r=>r.path.endsWith('/turns'));expect(submitted).toHaveLength(1);expect(submitted[0].headers['x-deepseek-api-key']).toBeUndefined();
 await page.getByRole('button',{name:'Cancel',exact:true}).click();await expect(page.locator('.agent-billing')).toContainText('0 / 10');
});
test('personal key can be forgotten, clears on navigation and fits mobile',async({page})=>{
 await backend(page);await page.setViewportSize({width:390,height:844});await page.goto('/enzymind/agent');
 await page.getByRole('button',{name:'Use my DeepSeek key'}).click();await page.locator('#deepseek-api-key').fill(token);await page.getByRole('button',{name:'Use this key',exact:true}).click();
 await page.getByRole('button',{name:'Forget key',exact:true}).click();await expect(page.locator('.agent-billing')).toContainText('0 / 10');
 await page.getByRole('button',{name:'Use my DeepSeek key'}).click();const box=await page.getByRole('dialog').boundingBox();expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(391);
 await page.screenshot({path:'/tmp/enzymind-billing-mobile.png',fullPage:true});
 await page.locator('#deepseek-api-key').fill(token);await page.getByRole('button',{name:'Use this key',exact:true}).click();
 await page.goto('/enzymind/');await page.goto('/enzymind/agent');await expect(page.getByRole('button',{name:'Forget key'})).toHaveCount(0);
});
